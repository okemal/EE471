from backend.app.catalogue import species_catalogue


def test_catalogue_is_complete_for_declared_reference():
    species = species_catalogue()
    assert len(species) == 41
    assert len({s["id"] for s in species}) == 41
    assert len({s["scientific_name"] for s in species}) == 41
    assert len({s["genus"] for s in species}) == 14
    assert sum(s["subfamily"] == "Pantherinae" for s in species) == 7
    assert any(s["scientific_name"] == "Felis catus" for s in species)
    for s in species:
        assert s["scientific_name"].split()[0] == s["genus"]
        assert s["source_url"].startswith("https://")
        assert len(s["identification"]) >= 2
        assert s["wikipedia_title"] and s["summary"] and s["range"]
