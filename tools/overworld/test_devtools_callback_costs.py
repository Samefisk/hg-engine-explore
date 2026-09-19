"""Exact fake-clock tests; no native runtime, sleeps or timing estimates."""
from copy import deepcopy
import gc
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools.overworld.devtools_callback_costs import CallbackCosts, MAX_LABELS, validate_callback_costs


class CallbackCostTests(unittest.TestCase):
    def test_hot_call_does_not_create_measurement_context(self):
        meter=self.meter(0,3)
        with patch.object(meter,"_measure",side_effect=AssertionError("hot allocation")):
            self.assertEqual(meter.call("native",lambda:7),7)
        self.assertEqual(meter.result(3)["measuredCpuNs"],3)

    def meter(self, *times):
        clock = iter(times)
        meter = CallbackCosts(lambda: next(clock))
        meter.begin_cycle()
        return meter

    def test_nested_callbacks_are_exclusive_and_forward_return_arguments(self):
        meter = self.meter(0, 2, 7, 10)
        def outer(a, *, b):
            return meter.call("main-queue-sampler", lambda: a+b)
        self.assertEqual(meter.call("native:0x02012340", outer, 4, b=5), 9)
        report = meter.result(12)
        self.assertEqual(report["categories"], {
            "native:0x02012340":{"cpuNs":5,"calls":1},
            "main-queue-sampler":{"cpuNs":5,"calls":1}})
        self.assertEqual(report["measuredCpuNs"],10)
        self.assertEqual(report["totalCpuNs"],12)

    def test_recursive_same_label_counts_each_call_without_double_time(self):
        meter = self.meter(10,11,13,14,16,20)
        meter.call("a", lambda: meter.call("a", lambda: meter.call("b",lambda:None)))
        self.assertEqual(meter.result(10)["categories"], {
            "a":{"cpuNs":9,"calls":2},"b":{"cpuNs":1,"calls":1}})

    def test_exceptions_are_charged_and_original_exception_is_preserved(self):
        meter = self.meter(0,2,5,8)
        error = RuntimeError("native failure")
        def fail(): raise error
        with self.assertRaises(RuntimeError) as caught:
            meter.call("parent", lambda: meter.call("child",fail))
        self.assertIs(caught.exception,error)
        self.assertEqual(meter.result(8)["categories"], {
            "parent":{"cpuNs":5,"calls":1},"child":{"cpuNs":3,"calls":1}})

    def test_bad_final_clock_does_not_mask_callback_exception(self):
        meter = self.meter(10,9)
        error = RuntimeError("first fault")
        def fail(): raise error
        with self.assertRaises(RuntimeError) as caught: meter.call("a",fail)
        self.assertIs(caught.exception,error)
        with self.assertRaises(ValueError): meter.result(100)

    def test_negative_wrong_type_and_reversed_clocks_fail(self):
        for times in ((-1,), (True,), (1.5,), (5,4)):
            with self.subTest(times=times):
                meter=self.meter(*times)
                with self.assertRaises(ValueError): meter.call("a",lambda:None)
                with self.assertRaises(ValueError): meter.result(100)

    def test_cycle_reset_and_results_are_detached(self):
        meter=self.meter(0,4,5,8)
        meter.call("a",lambda:None)
        first=meter.result(6);first["categories"]["a"]["cpuNs"]=0
        self.assertEqual(meter.result(6)["measuredCpuNs"],4)
        meter.begin_cycle();meter.call("b",lambda:None)
        self.assertEqual(meter.result(3)["categories"],{"b":{"cpuNs":3,"calls":1}})
        meter.begin_cycle();self.assertEqual(meter.result(0)["categories"],{})

    def test_reset_or_result_inside_callback_is_not_allowed(self):
        for operation in (lambda m:m.begin_cycle(),lambda m:m.result(20)):
            meter=self.meter(0,2)
            with self.assertRaises(ValueError):meter.call("a",lambda:operation(meter))
            self.assertEqual(meter.result(2)["categories"]["a"]["calls"],1)

    def test_label_bound_and_repeated_label(self):
        meter=CallbackCosts(lambda:0)
        for n in range(MAX_LABELS):meter.call(str(n),lambda:None)
        meter.call("0",lambda:None)
        with self.assertRaises(ValueError):meter.call("overflow",lambda:None)
        self.assertEqual(len(meter.result(0)["categories"]),MAX_LABELS)
        for label in ("", None, 1, "x"*129):
            with self.assertRaises(ValueError):meter.call(label,lambda:None)

    def test_raw_validation_rejects_bad_counts_bounds_and_scope(self):
        meter=self.meter(0,5);meter.call("a",lambda:None)
        report=meter.result(10)
        self.assertIs(validate_callback_costs(report,10),report)
        mutations = (
            lambda v:v.__setitem__("measuredCpuNs",4),
            lambda v:v.__setitem__("totalCpuNs",11),
            lambda v:v.__setitem__("schemaVersion",True),
            lambda v:v.__setitem__("scope","whole emulator"),
            lambda v:v["categories"]["a"].__setitem__("calls",0),
            lambda v:v["categories"]["a"].__setitem__("cpuNs",-1),
            lambda v:v["categories"]["a"].__setitem__("calls",True),
            lambda v:v.__setitem__("extra",1))
        for mutate in mutations:
            value=deepcopy(report);mutate(value)
            with self.assertRaises(ValueError):validate_callback_costs(value,10)
        with self.assertRaises(ValueError):meter.result(4)

    def test_gc_nested_exclusive_generations_and_scope_cleanup(self):
        callbacks=[]
        meter=self.meter(0,2,7,10)
        with patch("tools.overworld.devtools_callback_costs.gc",SimpleNamespace(callbacks=callbacks)):
            with meter.measure_gc():
                def sampler():
                    callbacks[0]("start",{"generation":1})
                    callbacks[0]("stop",{"generation":1})
                meter.call("sampler",sampler)
            self.assertEqual(callbacks,[])
        self.assertEqual(meter.result(10)["categories"],{
            "sampler":{"cpuNs":5,"calls":1},"gc:generation-1":{"cpuNs":5,"calls":1}})
        for generation in (0,2):
            meter=self.meter(0,4)
            with patch("tools.overworld.devtools_callback_costs.gc",SimpleNamespace(callbacks=callbacks)):
                with meter.measure_gc():
                    callbacks[0]("start",{"generation":generation})
                    callbacks[0]("stop",{"generation":generation})
            self.assertEqual(meter.result(4)["measuredCpuNs"],4)

    def test_gc_bad_notifications_latch_without_masking_original_error(self):
        for notifications in (("stop",), ("start","start"), ("start",)):
            meter=self.meter(0,2)
            callbacks=[];original=RuntimeError("native fault")
            with patch("tools.overworld.devtools_callback_costs.gc",SimpleNamespace(callbacks=callbacks)):
                with self.assertRaises(RuntimeError) as caught:
                    with meter.measure_gc():
                        for phase in notifications:callbacks[0](phase,{"generation":0})
                        raise original
            self.assertIs(caught.exception,original)
            self.assertEqual(callbacks,[]);self.assertEqual(meter._stack,[])
            with self.assertRaises(ValueError):meter.result(20)

    def test_gc_scope_is_single_and_ignores_other_threads(self):
        meter=self.meter();callbacks=[]
        with patch("tools.overworld.devtools_callback_costs.gc",SimpleNamespace(callbacks=callbacks)):
            with meter.measure_gc():
                with self.assertRaises(ValueError):
                    with meter.measure_gc():pass
                with patch("tools.overworld.devtools_callback_costs.threading.get_ident",return_value=-1):
                    callbacks[0]("start",{"generation":2})
                    callbacks[0]("stop",{"generation":2})
            self.assertEqual(callbacks,[])
        self.assertEqual(meter.result(0)["measuredCpuNs"],0)

    def test_gc_invalid_generation_phase_and_clock_fail_closed(self):
        for phase,info in (("start",{"generation":True}),
                           ("start",{"generation":3}),("other",{"generation":0})):
            meter=self.meter();callbacks=[]
            with patch("tools.overworld.devtools_callback_costs.gc",SimpleNamespace(callbacks=callbacks)):
                with meter.measure_gc():callbacks[0](phase,info)
            with self.assertRaises(ValueError):meter.result(20)
            self.assertEqual(callbacks,[])
        meter=self.meter(5,4);callbacks=[]
        with patch("tools.overworld.devtools_callback_costs.gc",SimpleNamespace(callbacks=callbacks)):
            with meter.measure_gc():
                callbacks[0]("start",{"generation":0})
                callbacks[0]("stop",{"generation":0})
        self.assertEqual(meter._stack,[])
        with self.assertRaises(ValueError):meter.result(20)

    def test_actual_bounded_cyclic_collection(self):
        meter=CallbackCosts();meter.begin_cycle()
        before=list(gc.callbacks);enabled=gc.isenabled();threshold=gc.get_threshold()
        cycle=[];cycle.append(cycle);del cycle
        start=time.thread_time_ns()
        with meter.measure_gc():
            meter.call("sampler",lambda:gc.collect(0))
        elapsed=time.thread_time_ns()-start
        report=meter.result(elapsed)
        self.assertGreaterEqual(report["categories"]["gc:generation-0"]["calls"],1)
        self.assertLessEqual(report["measuredCpuNs"],elapsed)
        self.assertEqual(gc.callbacks,before)
        self.assertEqual(gc.isenabled(),enabled);self.assertEqual(gc.get_threshold(),threshold)


if __name__ == "__main__": unittest.main()
