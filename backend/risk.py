from . import config

CONCERN = {
    "Plastic bag": 2,
    "Plastic bottle": 1,
    "Plastic waste": 2,
    "Plastic drum": 2,
    "Foam / discoloured water": 2,
    "Sewage / foam": 2,
    "Textile waste": 2,
    "Oil slick": 2,
    "Dead fish": 2,
    "Metal drum": 2,
    "Metal can": 1,
    "Thermocol": 1,
    "Fishing net": 1,
    "Water hyacinth": 1,
    "Bottle": 1,
    "Cup": 1,
    "Potted plant": 1,
}


def label_level(label):
    return CONCERN.get(label, 1)


def water_flags(ph, turb, tds):
    flags = []
    if ph is None or turb is None or tds is None:
        return flags
    if ph < config.PH_MIN or ph > config.PH_MAX:
        flags.append("pH")
    if turb > config.TURB_LIMIT:
        flags.append("turbidity")
    if tds > config.TDS_LIMIT:
        flags.append("TDS")
    return flags


def water_level(ph, turb, tds):
    flags = water_flags(ph, turb, tds)
    if not flags:
        return 0, flags
    severe = (
        (ph is not None and (ph < 6.0 or ph > 9.5))
        or (turb is not None and turb > 400)
        or (tds is not None and tds > 1400)
    )
    return (2 if severe else 1), flags
