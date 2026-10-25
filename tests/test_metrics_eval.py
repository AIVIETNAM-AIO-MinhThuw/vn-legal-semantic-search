import math
import random

from src.eval.metrics import evaluate, paired_bootstrap, per_query


def test_single_relevant_at_rank_2():
    m = per_query(["x", "a", "y"], {"a": 2})
    assert m["P@1"] == 0 and m["R@1"] == 0
    assert m["R@3"] == 1 and math.isclose(m["P@3"], 1 / 3)
    assert m["MRR@10"] == 0.5 and m["MAP@10"] == 0.5
    assert math.isclose(m["NDCG@10"], 1 / math.log2(3))


def test_no_hit_and_perfect():
    assert per_query(["x", "y"], {"a": 2})["NDCG@10"] == 0
    assert per_query(["a", "b"], {"a": 2, "b": 1})["NDCG@10"] == 1


def test_graded_ndcg_and_map_two_relevant():
    m = per_query(["b", "a"], {"a": 2, "b": 1})
    dcg = (2 ** 1 - 1) / 1 + (2 ** 2 - 1) / math.log2(3)
    idcg = (2 ** 2 - 1) / 1 + (2 ** 1 - 1) / math.log2(3)
    assert math.isclose(m["NDCG@10"], dcg / idcg)
    assert m["MAP@10"] == 1.0


def test_depth_cutoff_and_queries_without_positive_skipped():
    ranked = [f"x{i}" for i in range(10)] + ["a"]
    assert per_query(ranked, {"a": 2})["R@10"] == 0
    mean, per = evaluate({"q1": ["a"], "q2": ["b"]}, {"q1": {"a": 2}, "q2": {}}, ["q1", "q2"])
    assert mean["n_queries"] == 1 and set(per) == {"q1"}


def test_bootstrap_identical_systems():
    per = {f"q{i}": {"NDCG@10": random.Random(i).random()} for i in range(50)}
    r = paired_bootstrap(per, per, "NDCG@10", n=200)
    assert r["diff"] == 0 and r["ci95"] == [0, 0]
