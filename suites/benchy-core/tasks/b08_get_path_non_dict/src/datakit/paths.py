"""Read values out of nested dictionaries with dotted paths."""


def get_path(data, path, default=None):
    """Return data['a']['b'] for path 'a.b', or `default` when the path does not exist."""
    current = data
    for key in path.split("."):
        if key not in current:
            return default
        current = current[key]
    return current
