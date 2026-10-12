import unittest

from app.geocoding import get_english_place_name, normalize_search_results


class GeocodingTests(unittest.TestCase):
    def test_same_name_in_different_countries_is_preserved(self):
        places = [
            {"name": "Siberia", "osm_type": "node", "osm_id": index,
             "address": {"country": country, "county": "Local county"}}
            for index, country in enumerate(
                ["Italy", "United States", "United States", "Colombia",
                 "Colombia", "New Zealand", "Russia"], start=1
            )
        ]
        results = normalize_search_results(places, 10)
        self.assertEqual(len(results), 7)
        self.assertEqual(results[6]["address"]["country"], "Russia")
        self.assertTrue(all(item["name"] == "Siberia" for item in results))

    def test_repeated_entity_is_removed_but_same_id_other_type_survives(self):
        place = {"name": "Siberia", "osm_type": "node", "osm_id": 1}
        relation = {**place, "osm_type": "relation"}
        self.assertEqual(len(normalize_search_results([place, place, relation], 10)), 2)

    def test_distinct_coordinates_survive_without_osm_identity(self):
        places = [{"name": "Siberia", "lat": lat, "lon": "10"} for lat in ["20", "30"]]
        self.assertEqual(len(normalize_search_results(places, 10)), 2)

    def test_english_name_preferred_and_original_address_kept(self):
        place = {"name": "Сибирь", "namedetails": {"name:en": "Siberia"},
                 "display_name": "Сибирь, Russia", "address": {"country": "Russia"}}
        result = normalize_search_results([place], 10)[0]
        self.assertEqual(result["display_name_en"], "Siberia")
        self.assertEqual(result["display_name_original"], "Сибирь, Russia")
        self.assertEqual(place["name"], "Сибирь")

    def test_result_limit_and_name_fallback(self):
        self.assertEqual(get_english_place_name({"address": {"country": "Russia"}}), "Russia")
        places = [{"name": "Place", "osm_type": "node", "osm_id": i} for i in range(15)]
        self.assertEqual(len(normalize_search_results(places, 10)), 10)


if __name__ == "__main__":
    unittest.main()
