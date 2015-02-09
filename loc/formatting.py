
def _get_formatting_parts(geocode):
    geocode = geocode.copy()

    components = [
        geocode.get_component('neighborhood'),
        geocode.get_component('sublocality'),
    ]
    country = geocode.get_component('country')
    if country in ['United States', 'Canada', 'Australia', 'Mexico', 'Malaysia', 'Japan', 'Hong Kong']:
        mini_components = [
            geocode.get_component('locality'),
            geocode.get_component('administrative_area_level_1', long=False),
            ]
        components.append(', '.join(x for x in mini_components if x))
    else:
        components.extend([
            geocode.get_component('locality'),
        ])
    components.extend([
        geocode.get_component('country'),
    ])
    geocode.delete_component('neighborhood')
    geocode.delete_component('sublocality')
    geocode.delete_component('locality')
    geocode.delete_component('administrative_area_level_1')
    geocode.delete_component('country')
    components = [
        geocode.get_component('colloquial_area'),
    ] + components + [
        geocode.get_component('continent'),
    ]

    return [x for x in components if x]

def _format_from_parts(parts):
    return ', '.join(parts)

def format_geocode(geocode):
    return _format_from_parts(_get_formatting_parts(geocode))

def format_geocodes(geocodes):
    if geocodes == []:
        return []
    parts_list = [_get_formatting_parts(geocode) for geocode in geocodes]
    min_length = min(len(x) for x in parts_list)
    # If all our addresses are in the same country, or state, then trim that off as irrelevant
    for i in range(min_length-1):
        # Get the set of the 'last' element of each of our addresses
        index_parts = set([x[-1] for x in parts_list])
        # If they all are the same thing, let's trim it off as unnecessary
        if len(index_parts) == 1:
            for x in parts_list:
                x.pop()
    # Now grab the last two pieces of data, as being relevant to where we are.
    # Anything earlier than that in the list, is too specific at the scale we are currently at.
    parts_list = [x[-2:] for x in parts_list]
    addresses_list = [_format_from_parts(x) for x in parts_list]
    return addresses_list
