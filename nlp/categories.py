import keywords
import grammar
from grammar import Any

ANY_BREAK = Any(
    keywords.STYLE_BREAK,
    keywords.STYLE_BREAK_WEAK,
    'break\w*',
    keywords.BBOY_CREW[grammar.STRONG_WEAK],
    keywords.BBOY_DANCER[grammar.STRONG_WEAK],
)

ANY_POP = Any(
    keywords.STYLE_POP,
    # These two were omitted from the above,
    # since they are not strong enough on their own.
    # But given a dance event, they can be a very strong classifier.
    keywords.STYLE_POP_WEAK,
    "pop\w*",
)

ANY_LOCK = Any(
    keywords.STYLE_LOCK,
    "lock\w*",
)

# No extras needed here
ANY_WAACK = Any(
    keywords.STYLE_WAACK,
    "[uw]h?aa?c?c?k\w*",
    "punk\w*",
)

ANY_HOUSE = Any(
    keywords.STYLE_HOUSE,
    keywords.HOUSE, # TODO: Rename to STYLE_HOUSE_WEAK,
    "hous\w+",
)

ANY_HIPHOP = Any(
    keywords.STYLE_HIPHOP,
    keywords.STYLE_HIPHOP_WEAK,
    'hip\Whop\w*',
)

ANY_DANCEHALL = Any(
    keywords.STYLE_DANCEHALL,
    keywords.STYLE_DANCEHALL_WEAK,
)

ANY_KRUMP = Any(
    keywords.STYLE_KRUMP,
    'krump\w*',
)

ANY_TURF = Any(
    keywords.STYLE_TURF,
    'turf\w*',
)

ANY_LITEFEET = Any(
    keywords.STYLE_LITEFEET,
    'lite\w?\w*',
)

ANY_FLEX = Any(
    keywords.STYLE_FLEX,
    'flex\w*',
)

ANY_BEBOP = Any(
    keywords.STYLE_BEBOP,
    keywords.STYLE_BEBOP_WEAK,
    'jazz\Wfusion',
)


ANY_ALLSTYLE = Any(
    keywords.STYLE_ALLSTYLE,
    keywords.STYLE_ALLSTYLE_WEAK,
    keywords.FREESTYLE,
    'all\W+style\w+',
)

ANY_VOGUE = Any(
    keywords.VOGUE,
    keywords.EASY_VOGUE,
)

STYLES = {
    'BREAK': ANY_BREAK,
    'POP': ANY_POP,
    'LOCK': ANY_LOCK,
    'WAACK': ANY_WAACK,
    'HOUSE': ANY_HOUSE,
    'HIPHOP': ANY_HIPHOP,
    'DANCEHALL': ANY_DANCEHALL,
    'KRUMP': ANY_KRUMP,
    'TURF': ANY_TURF,
    'LITEFEET': ANY_LITEFEET,
    'FLEX': ANY_FLEX,
    'BEBOP': ANY_BEBOP,
    'ALLSTYLE': ANY_ALLSTYLE,
    'VOGUE': ANY_VOGUE,
}


def find_styles(classified_event):
    styles = set()
    for style, rule in STYLES.iteritems():
        if classified_event.processed_title.get_tokens(rule):
            styles.add(style)
    if styles:
        return styles
    for style, rule in STYLES.iteritems():
        if classified_event.processed_text.get_tokens(rule):
            styles.add(style)
    return styles