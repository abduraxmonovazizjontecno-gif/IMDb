from django import template

register = template.Library()


@register.filter
def millions(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    if value is None:
        return None
    if value >= 1_000_000_000:
        return f"${value / 1_000_000_000:.1f}B"
    if value >= 1_000_000:
        return f"${value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"${value / 1_000:.0f}K"
    return f"${value:.0f}"
