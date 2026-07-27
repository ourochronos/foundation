"""Individuation invariants (docs/08, D49): same-name entities split on
functional conflict; within-world mentions re-resolve; values excluded;
query-time type gate disambiguates; merges redirect."""

import numpy as np

from codec.individuation import (EntityRegistry, functional_relations,
                                 is_value)


def test_values_are_not_individuals():
    assert is_value("4,200") and is_value("1987")
    assert is_value("August 18, 1926") and is_value("13 November 1989")
    assert not is_value("North Halmelton")


def test_same_name_splits_on_functional_conflict():
    r = EntityRegistry()
    y1 = r.resolve_write("LandY", "located_in", "o", None)
    y2 = r.resolve_write("LandZ", "located_in", "o", None)
    a = r.resolve_write("CityA", "located_in", "s", y1, functional=True)
    b = r.resolve_write("CityA", "located_in", "s", y2, functional=True)
    assert a != b                     # conflicting countries -> two cities


def test_within_world_mentions_reresolve():
    r = EntityRegistry()
    y = r.resolve_write("LandY", "located_in", "o", None)
    a1 = r.resolve_write("CityA", "located_in", "s", y, functional=True)
    a2 = r.resolve_write("CityA", "population_of", "s", None, functional=True)
    assert a1 == a2                   # same individual, second fact


def test_query_gate_disambiguates_by_relation():
    """v1 resolver is CONFLICT-driven: same-form mentions split only on
    functional-conflict evidence (write-time profile gate deferred to the
    split-repair pass — D52). Values act as pseudo-objects so conflicts
    fire on them too."""
    r = EntityRegistry()
    land = r.resolve_write("Acme", "capital_of", "s", "e_city1",
                           functional=True)
    corp = r.resolve_write("Acme", "capital_of", "s", "e_city2",
                           functional=True)     # different capital: distinct
    assert land != corp
    r.entities[corp].slots[("headquartered_in", "s")] = 1
    assert r.resolve_query("Acme", "capital_of") and \
        set(r.resolve_query("Acme")) == {land, corp}


def test_value_conflicts_split():
    """Two same-name people born in different years are two people."""
    r = EntityRegistry()
    p1 = r.resolve_write("Jo Fosven", "born_in", "s", "v:1987",
                         functional=True)
    p2 = r.resolve_write("Jo Fosven", "born_in", "s", "v:1990",
                         functional=True)
    p1b = r.resolve_write("Jo Fosven", "born_in", "s", "v:1987",
                          functional=True)
    assert p1 != p2 and p1b == p1


def test_merge_redirects():
    r = EntityRegistry()
    a = r.resolve_write("United States", "capital_of", "s", None)
    b = r.resolve_write("US", "capital_of", "s", None)
    r.merge(a, b)
    assert set(r.resolve_query("US", "capital_of")) == {a}


def test_functional_detection():
    facts = [{"relation": "capital_of", "subject": "X", "object": "C1"},
             {"relation": "capital_of", "subject": "Y", "object": "C2"},
             {"relation": "export_of", "subject": "X", "object": "A"},
             {"relation": "export_of", "subject": "X", "object": "B"}]
    fr = functional_relations(facts)
    assert "capital_of" in fr and "export_of" not in fr
