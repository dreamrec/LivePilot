"""
LivePilot - Browser domain handlers (6 commands).
"""

import Live

from .router import register
from .utils import get_track


def _get_browser():
    """Get the browser from the Application object (not Song)."""
    return Live.Application.get_application().browser


def _get_categories(browser):
    """Return a dict of browser category name -> browser item.

    Includes all documented Browser properties from the Live Object Model:
    instruments, audio_effects, midi_effects, sounds, drums, samples,
    packs, user_library, plugins, max_for_live, clips, current_project.
    """
    categories = {
        "instruments": browser.instruments,
        "audio_effects": browser.audio_effects,
        "midi_effects": browser.midi_effects,
        "sounds": browser.sounds,
        "drums": browser.drums,
        "samples": browser.samples,
        "packs": browser.packs,
        "user_library": browser.user_library,
    }
    # Additional categories — may not exist on older Live versions
    for attr in ("plugins", "max_for_live", "clips", "current_project"):
        try:
            val = getattr(browser, attr)
            if val is not None:
                categories[attr] = val
        except AttributeError:
            pass
    return categories


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


_MAX_SEARCH_ITERATIONS = 100000


def _search_recursive(item, name_filter, loadable_only, results, depth, max_depth,
                      max_results=100, _counter=None):
    """Recursively search browser children with iteration cap."""
    if _counter is None:
        _counter = [0]  # mutable counter shared across recursion
    if depth > max_depth or len(results) >= max_results:
        return
    for child in item.children:
        _counter[0] += 1
        if _counter[0] > _MAX_SEARCH_ITERATIONS or len(results) >= max_results:
            return
        match = True
        if name_filter and name_filter.lower() not in child.name.lower():
            match = False
        if loadable_only and not child.is_loadable:
            match = False
        if match:
            entry = {
                "name": child.name,
                "is_loadable": child.is_loadable,
            }
            try:
                entry["uri"] = child.uri
            except AttributeError:
                entry["uri"] = None
            results.append(entry)
        if child.is_folder:
            _search_recursive(
                child, name_filter, loadable_only, results, depth + 1, max_depth,
                max_results, _counter
            )
            if len(results) >= max_results:
                return


@register("get_browser_tree")
def get_browser_tree(song, params):
    """Return an overview of the browser categories."""
    category_type = str(params.get("category_type", "all")).lower()
    browser = _get_browser()
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
        # Count lazily without materializing the full children list
        children_preview = []
        count = 0
        for c in item.children:
            count += 1
            if len(children_preview) < 20:
                children_preview.append(c.name)
        result.append({
            "name": name,
            "children_count": count,
            "children_preview": children_preview,
        })
    return {"categories": result}


@register("get_browser_items")
def get_browser_items(song, params):
    """List items at a browser path."""
    path = str(params["path"])
    browser = _get_browser()
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
            except AttributeError:
                entry["uri"] = None
        result.append(entry)
    return {"path": path, "items": result}


@register("search_browser")
def search_browser(song, params):
    """Search the browser tree by name filter."""
    path = str(params["path"])
    name_filter = params.get("name_filter", None)
    loadable_only = bool(params.get("loadable_only", False))
    max_depth = int(params.get("max_depth", 8))
    max_results = int(params.get("max_results", 100))
    browser = _get_browser()
    item = _navigate_path(browser, path)

    results = []
    _search_recursive(item, name_filter, loadable_only, results, 0, max_depth,
                      max_results)
    truncated = len(results) >= max_results
    result = {"path": path, "items": results, "total_results": len(results)}
    if truncated:
        result["truncated"] = True
        result["max_results"] = max_results
    # Legacy alias for backward compatibility
    result["results"] = results
    result["count"] = len(results)
    return result


@register("load_browser_item")
def load_browser_item(song, params):
    """Load a browser item onto a track by URI.

    First tries URI-based matching (exact child.uri comparison).
    Falls back to name extraction from the URI's last path segment.
    Searches all browser categories including user_library and samples.
    """
    track_index = int(params["track_index"])
    uri = str(params["uri"])
    track = get_track(song, track_index)
    browser = _get_browser()

    # Parse category hint from URI (e.g., "query:Drums#..." -> prioritize drums)
    _category_map = {
        "drums": "drums", "samples": "samples", "instruments": "instruments",
        "audiofx": "audio_effects", "audio_effects": "audio_effects",
        "midifx": "midi_effects", "midi_effects": "midi_effects",
        "sounds": "sounds", "packs": "packs",
        "userlibrary": "user_library", "user_library": "user_library",
        "plugins": "plugins", "max_for_live": "max_for_live",
    }
    priority_attr = None
    if ":" in uri:
        # Extract category from "query:Drums#..." or "query:UserLibrary#..."
        after_colon = uri.split(":", 1)[1]
        cat_hint = after_colon.split("#", 1)[0].lower().replace(" ", "_")
        priority_attr = _category_map.get(cat_hint)

    # Build category search order — prioritize the category from the URI
    category_attrs = [
        "user_library", "plugins", "max_for_live", "samples",
        "instruments", "audio_effects", "midi_effects", "packs",
        "sounds", "drums",
    ]
    if priority_attr and priority_attr in category_attrs:
        category_attrs.remove(priority_attr)
        category_attrs.insert(0, priority_attr)

    categories = []
    for attr in category_attrs:
        try:
            categories.append(getattr(browser, attr))
        except AttributeError:
            pass

    _iterations = [0]
    MAX_ITERATIONS = 50000

    # ── Strategy 1: match by URI directly ────────────────────────────
    def find_by_uri(parent, target_uri, depth=0):
        if depth > 8 or _iterations[0] > MAX_ITERATIONS:
            return None
        try:
            children = list(parent.children)
        except AttributeError:
            return None
        for child in children:
            _iterations[0] += 1
            if _iterations[0] > MAX_ITERATIONS:
                return None
            try:
                if child.uri == target_uri and child.is_loadable:
                    return child
            except AttributeError:
                pass
            result = find_by_uri(child, target_uri, depth + 1)
            if result is not None:
                return result
        return None

    for category in categories:
        _iterations[0] = 0  # Reset counter per category to avoid premature cutoff
        found = find_by_uri(category, uri)
        if found is not None:
            song.view.selected_track = track
            browser.load_item(found)
            device_count = len(list(track.devices))
            return {
                "track_index": track_index,
                "loaded": True,
                "name": found.name,
                "device_count": device_count,
            }

    # ── Strategy 2: extract name from URI, search by name ────────────
    device_name = uri
    if "#" in uri:
        device_name = uri.split("#", 1)[1]
    # For Sounds URIs like "Pad:FileId_6343", strip the FileId part
    # and use the subcategory or the full fragment for matching
    if "FileId_" in device_name:
        # URI contains an internal file ID — name-based search won't work.
        # Try one more URI pass with a much higher iteration limit.
        _iterations[0] = 0
        DEEP_MAX = 200000
        def find_by_uri_deep(parent, target_uri, depth=0):
            if depth > 12 or _iterations[0] > DEEP_MAX:
                return None
            try:
                children = list(parent.children)
            except AttributeError:
                return None
            for child in children:
                _iterations[0] += 1
                if _iterations[0] > DEEP_MAX:
                    return None
                try:
                    if child.uri == target_uri and child.is_loadable:
                        return child
                except AttributeError:
                    pass
                result = find_by_uri_deep(child, target_uri, depth + 1)
                if result is not None:
                    return result
            return None

        for category in categories:
            _iterations[0] = 0
            found = find_by_uri_deep(category, uri)
            if found is not None:
                song.view.selected_track = track
                browser.load_item(found)
                device_count = len(list(track.devices))
                return {
                    "track_index": track_index,
                    "loaded": True,
                    "name": found.name,
                    "device_count": device_count,
                }

        raise ValueError(
            "Item '%s' not found in browser (FileId URI — try "
            "search_browser to find the item, then use find_and_load_device "
            "with the exact name instead)" % uri
        )

    for sep in (":", "/"):
        if sep in device_name:
            device_name = device_name.rsplit(sep, 1)[1]
    # URL-decode
    try:
        from urllib.parse import unquote
        device_name = unquote(device_name)
    except ImportError:
        device_name = device_name.replace("%20", " ")
    # Strip file extensions
    for ext in (".amxd", ".adv", ".adg", ".aupreset", ".als", ".wav", ".aif", ".aiff", ".mp3"):
        if device_name.lower().endswith(ext):
            device_name = device_name[:-len(ext)]
            break

    target = device_name.lower()
    _iterations[0] = 0

    def find_by_name(parent, depth=0):
        if depth > 8 or _iterations[0] > MAX_ITERATIONS:
            return None
        try:
            children = list(parent.children)
        except AttributeError:
            return None
        for child in children:
            _iterations[0] += 1
            if _iterations[0] > MAX_ITERATIONS:
                return None
            child_lower = child.name.lower()
            if (child_lower == target or target in child_lower) and child.is_loadable:
                return child
            result = find_by_name(child, depth + 1)
            if result is not None:
                return result
        return None

    for category in categories:
        found = find_by_name(category)
        if found is not None:
            song.view.selected_track = track
            browser.load_item(found)
            device_count = len(list(track.devices))
            return {
                "track_index": track_index,
                "loaded": True,
                "name": found.name,
                "device_count": device_count,
            }

    raise ValueError(
        "Item '%s' not found in browser" % device_name
    )


_SCAN_MAX_ITERATIONS = 100000


def _scan_recursive(item, results, depth, max_depth, max_per_category,
                    _counter=None):
    """Recursively collect loadable browser items with iteration cap."""
    if _counter is None:
        _counter = [0]
    if depth > max_depth or len(results) >= max_per_category:
        return
    for child in item.children:
        _counter[0] += 1
        if _counter[0] > _SCAN_MAX_ITERATIONS or len(results) >= max_per_category:
            return
        if child.is_loadable:
            entry = {"name": child.name, "is_loadable": True}
            try:
                entry["uri"] = child.uri
            except AttributeError:
                entry["uri"] = None
            results.append(entry)
        if child.is_folder:
            _scan_recursive(
                child, results, depth + 1, max_depth, max_per_category,
                _counter
            )
            if len(results) >= max_per_category:
                return


@register("scan_browser_deep")
def scan_browser_deep(song, params):
    """Walk the entire browser tree and return all loadable items by category.

    Parameters
    ----------
    max_per_category : int, optional
        Maximum items to collect per top-level category (default 1000).
    max_depth : int, optional
        Maximum recursion depth into the browser tree (default 4).
    """
    max_per_category = int(params.get("max_per_category", 1000))
    max_depth = int(params.get("max_depth", 4))
    browser = _get_browser()
    categories = _get_categories(browser)

    result = {}
    for cat_name, cat_item in categories.items():
        items = []
        _scan_recursive(cat_item, items, 0, max_depth, max_per_category)
        result[cat_name] = items

    return {"categories": result}


@register("get_device_presets")
def get_device_presets(song, params):
    """List available presets for a device type by searching the browser.

    Searches up to 2 levels deep inside the device folder to find presets,
    since Ableton nests them inside sub-folders like 'Default Presets'.
    """
    device_name = str(params["device_name"])
    browser = _get_browser()

    categories = {
        "audio_effects": browser.audio_effects,
        "instruments": browser.instruments,
        "midi_effects": browser.midi_effects,
    }
    results = []
    found_category = None

    def collect_presets(item, depth=0):
        """Recursively collect loadable presets up to depth 2."""
        if depth > 2:
            return
        try:
            children = list(item.children)
        except AttributeError:
            return
        for child in children:
            if child.is_loadable and not child.is_folder:
                entry = {"name": child.name}
                try:
                    entry["uri"] = child.uri
                except AttributeError:
                    entry["uri"] = None
                results.append(entry)
            elif child.is_folder:
                collect_presets(child, depth + 1)

    for cat_name, cat_item in categories.items():
        for item in cat_item.children:
            if item.name.lower() == device_name.lower():
                found_category = cat_name
                collect_presets(item)
                break
        if found_category:
            break
    return {
        "device_name": device_name,
        "category": found_category,
        "presets": results,
    }
