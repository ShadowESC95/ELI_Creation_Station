"""The rule: the main model stays loaded; a specialist loads for a job and unloads when idle."""

from __future__ import annotations

from dataclasses import replace

import pytest

from eli_creation.models.catalogue import Catalogue, ModelSpec
from eli_creation.models.manager import ModelManager, Refused
from eli_creation.models.residency import Policy
from eli_creation.tiers import machine_from_dict


class Main:
    source, name, available, state, why_unavailable = "gguf", "main", True, "ready", ""

    def __init__(self, memory_mb=5000, device="gpu:0"):
        self.memory_mb, self.device, self.suspended, self.resumed = memory_mb, device, 0, 0

    def suspend(self):
        self.suspended += 1
        self.state = "unloaded"

    def resume(self):
        self.resumed += 1
        self.state = "ready"


class FakeWorker:
    log: list[str] = []

    def __init__(self, spec, device):
        self.spec, self.device, self.alive = spec, device, False

    def start_and_load(self):
        self.alive = True
        FakeWorker.log.append(f"load {self.spec.id} {self.device}")
        return {}

    def call(self, method, args, *, timeout=None):
        return {"method": method, "device": self.device}

    def stop(self):
        self.alive = False
        FakeWorker.log.append(f"stop {self.spec.id}")


def spec(model_id, memory_mb, *, cpu_ok=False, ram_mb=0):
    return ModelSpec(model_id, model_id, "specialist", ("image",), "Apache-2.0", memory_mb=memory_mb, ram_mb=ram_mb,
                     backends=("cuda",), cpu_ok=cpu_ok, adapter="eli_creation.engines.adapters.fake:FakeModel")


@pytest.fixture()
def clock():
    return {"t": 0.0}


def manager(clock, *, specs, policy=None, main=None, gpus=(8192,), ram=16384):
    machine = machine_from_dict({"ram_mb": ram, "available_ram_mb": ram, "accelerators": [
        {"index": i, "vendor": "nvidia", "name": f"card {i}", "kind": "discrete", "memory_mb": mb, "free_mb": mb,
         "backends": ["cuda"]} for i, mb in enumerate(gpus)]})
    FakeWorker.log = []
    return ModelManager(machine, Catalogue(tuple(specs)), policy or Policy(idle_unload_seconds=60, reserve_mb=0),
                        main=main or Main(), launcher=FakeWorker, clock=lambda: clock["t"])


def test_a_specialist_loads_for_its_job_and_the_main_model_stays(clock):
    main = Main()
    m = manager(clock, specs=[spec("img", 2500)], main=main)
    assert m.resident_ids() == []
    with m.use("img") as model:
        assert model.call("generate")["device"] == "gpu:0"
        assert m.resident_ids() == ["img"]
    assert main.suspended == 0 and main.state == "ready"


def test_an_idle_specialist_is_unloaded_after_the_policy_time(clock):
    m = manager(clock, specs=[spec("img", 2500)])
    with m.use("img"):
        pass
    clock["t"] = 30
    assert m.unload_idle() == []
    clock["t"] = 61
    assert m.unload_idle() == ["img"]
    assert FakeWorker.log[-1] == "stop img"


def test_zero_idle_time_unloads_as_soon_as_the_job_ends(clock):
    m = manager(clock, specs=[spec("img", 2500)], policy=Policy(idle_unload_seconds=0, reserve_mb=0))
    with m.use("img"):
        pass
    assert m.resident_ids() == []


def test_a_second_card_is_used_before_anything_is_unloaded(clock):
    main = Main(memory_mb=6000, device="gpu:0")
    m = manager(clock, specs=[spec("big", 6000)], main=main, gpus=(8192, 8192))
    with m.use("big") as model:
        assert model.device == "gpu:1"
    assert main.suspended == 0


def test_the_longest_idle_specialist_makes_way(clock):
    m = manager(clock, specs=[spec("a", 2000), spec("b", 2000)], policy=Policy(max_resident_specialists=1, reserve_mb=0))
    with m.use("a"):
        pass
    with m.use("b"):
        pass
    assert m.resident_ids() == ["b"]
    assert "stop a" in FakeWorker.log


def test_too_big_beside_the_main_model_is_refused_with_the_reason(clock):
    main = Main(memory_mb=6000)
    m = manager(clock, specs=[spec("big", 6000)], main=main)
    with pytest.raises(Refused) as caught:
        with m.use("big"):
            pass
    assert "beside the main model" in str(caught.value) and "step aside" in str(caught.value)
    assert main.suspended == 0, "the main model is never unloaded unless the person allowed it"


def test_the_main_model_steps_aside_only_when_allowed_and_comes_back(clock):
    main = Main(memory_mb=6000)
    m = manager(clock, specs=[spec("big", 6000)], main=main, policy=Policy(allow_main_swap=True, reserve_mb=0))
    with m.use("big"):
        assert main.suspended == 1 and main.state == "unloaded"
    assert main.resumed == 1 and main.state == "ready"
    assert m.resident_ids() == [], "a model the main model stepped aside for goes when its job is done"


def test_the_processor_takes_a_model_that_may_run_there(clock):
    main = Main(memory_mb=7000)
    m = manager(clock, specs=[spec("img", 6000, cpu_ok=True, ram_mb=9000)], main=main)
    with m.use("img") as model:
        assert model.device == "cpu"


def test_a_planned_model_is_not_loaded(clock):
    m = manager(clock, specs=[replace(spec("later", 100), status="planned")])
    with pytest.raises(Refused, match="planned"):
        with m.use("later"):
            pass
