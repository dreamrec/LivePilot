"""
LivePilot - Browser domain handlers (4 commands).
"""

from .router import register
from .utils import get_track


def _get_categories(browser):
    """Return a dict of browser category name -> browser item."""
    return {
        "instruments": browser.instruments,
        "audio_effects": browser.audio_effects,
        "midi_effects": browser.midi_effects,
        "sounds": browser.sounds,
        "drums": browser.drums,
        "samples": browser.samples,
        "packs": browser.packs,
        "user_library": browser.user_library,
    }


def _navigate_path(browser, path):
    """Walk the browser tree by slash-separated path, return the item."""
    categories = _get_categories(browser)
    parts = [p.strip() for p in path.strip("/").split("/") if p.strip()]
    if not parts:
        raise ValueError("Path cannot be empty")

    # First part must be a category name
    first = parts[0].lower()
    if first not in categories:
        raise ValueError(
            "Unknown category '%s'. Available: %s"
            % (first, ", ".join(sorted(categories.keys())))
        )
    current = categories[first]

    # Walk remaining parts by child name
    for part in parts[1:]:
        children = list(current.children)
        matched = None
        for child in children:
            if child.name == part:
                matched = child
                break
        if matched is None:
            child_names = [c.name for c in children[:20]]
            raise ValueError(
                "Item '%s' not found in '%s'. Available: %s"
                % (part, current.name, ", ".join(child_names))
            )
        current = matched

    return current


def _search_recursive(item, name_filter, loadable_only, results, depth, max_depth):
    """Recursively search browser children."""
    if depth > max_depth or len(results) >= 50:
        return
    for child in item.children:
        if len(results) >= 50:
            return
        match = True
        if name_filter and name_filter.lower() not in child.name.lower():
            match = False
        if loadable_only and not child.is_loadable:
            match = False
        if match and (not loadable_only or child.is_loadable):
            entry = {
                "name": child.name,
                "is_loadable": child.is_loadable,
            }
            try:
                entry["uri"] = child.uri
            except Exception:
                entry["uri"] = None
            results.append(entry)
        if child.is_folder:
            _search_recursive(
                child, name_filter, loadable_only, results, depth + 1, max_depth
            )


@register("get_browser_tree")
def get_browser_tree(song, params):
    """Return an overview of the browser categories."""
    category_type = str(params.get("category_type", "all")).lower()
    browser = song.browser
    categories = _get_categories(browser)

    if category_type != "all":
        if category_type not in categories:
            raise ValueError(
                "Unknown category '%s'. Available: %s"
                % (category_type, ", ".join(sorted(categories.keys())))
            )
        categories = {category_type: categories[category_type]}

    result = []
    for name, item in categories.items():
        children = list(item.children)
        child_names = [c.name for c in children[:20]]
        result.append({
            "name": name,
            "children_count": len(children),
            "children_preview": child_names,
        })
    return {"categories": result}


@register("get_browser_items")
def get_browser_items(song, params):
    """List items at a browser path."""
    path = str(params["path"])
    browser = song.browser
    item = _navigate_path(browser, path)

    result = []
    for child in item.children:
        entry = {
            "name": child.name,
            "is_loadable": child.is_loadable,
            "is_folder": child.is_folder,
        }
        if child.is_loadable:
            try:
                entry["uri"] = child.uri
            except Exception:
                entry["uri"] = None
        result.append(entry)
    return {"path": path, "items": result}


@register("search_browser")
def search_browser(song, params):
    """Search the browser tree by name filter."""
    path = str(params["path"])
    name_filter = params.get("name_filter", None)
    loadable_only = bool(params.get("loadable_only", False))
    browser = song.browser
    item = _navigate_path(browser, path)

    results = []
    _search_recursive(item, name_filter, loadable_only, results, 0, 4)
    return {"path": path, "results": results, "count": len(results)}


@register("load_browser_item")
def load_browser_item(song, params):
    """Load a browser item onto a track by URI."""
    track_index = int(params["track_index"])
    uri = str(params["uri"])
    track = get_track(song, track_index)
    browser = song.browser

    # Select the target track so the item loads onto it
    song.view.selected_track = track
    try:
        browser.load_item_by_uri(uri)
    except AttributeError:
        raise ValueError(
            "load_item_by_uri not available in this Live version"
        )

    device_count = len(list(track.devices))
    return {
        "track_index": track_index,
        "loaded": True,
        "device_count": device_count,
    }
