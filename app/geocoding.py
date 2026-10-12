def get_english_place_name(
    data: dict
) -> str:
    namedetails = (
        data.get("namedetails")
        or {}
    )

    address = (
        data.get("address")
        or {}
    )

    english_name = (
        namedetails.get("name:en")
        or namedetails.get(
            "official_name:en"
        )
        or namedetails.get(
            "short_name:en"
        )
    )

    if english_name:
        return english_name

    place_name = (
        data.get("name")
        or address.get("city")
        or address.get("town")
        or address.get("village")
        or address.get("hamlet")
        or address.get(
            "municipality"
        )
        or address.get("county")
        or address.get("state")
        or address.get("country")
    )

    if place_name:
        return place_name

    return data.get(
        "display_name",
        "Unknown location",
    )


def normalize_search_results(results: list[dict], limit: int) -> list[dict]:
    normalized = []
    seen = set()
    for result in results:
        item = dict(result)
        # Names are not unique: distinct places called Siberia must survive.
        if item.get("osm_type") is not None and item.get("osm_id") is not None:
            identity = (item["osm_type"], str(item["osm_id"]))
        else:
            identity = ("coordinates", str(item.get("lat")), str(item.get("lon")),
                        item.get("display_name", item.get("name", "")))
        if identity in seen:
            continue
        seen.add(identity)
        item["display_name_original"] = item.get("display_name")
        name = get_english_place_name(item)
        item["name"] = name
        item["display_name_en"] = name
        normalized.append(item)
        if len(normalized) >= limit:
            break
    return normalized
