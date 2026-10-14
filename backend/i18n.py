STRINGS = {
    "wastewater": {
        "en": "Wastewater event: pH {ph}, TDS {tds} ppm at {segment}. Risk HIGH. Lab test requested.",
        "ta": "கழிவுநீர் எச்சரிக்கை: pH {ph}, TDS {tds} ppm, {segment}. ஆபத்து அதிகம். ஆய்வக சோதனை கோரப்பட்டுள்ளது.",
    },
    "surge": {
        "en": "SURGE: water rising {rate:.0f} m/hour. People at the ghat must leave the water now. "
              "Wave reaches the ghat in about {min} minutes (sensor 5 km upstream).",
        "ta": "வெள்ள எச்சரிக்கை: நீர்மட்டம் மணிக்கு {rate:.0f} மீட்டர் வேகமாக உயர்கிறது. படித்துறையில் இருப்பவர்கள் உடனே வெளியேறுங்கள். {min} நிமிடத்தில் வரும். (சென்சார் 5 கி.மீ. மேலே).",
    },
    "arrived": {
        "en": "Flood wave has arrived at the ghat. Siren stands down. Keep people away from the river.",
        "ta": "அலை படித்துறையை அடைந்தது. சைரன் நிறுத்தப்பட்டது. ஆற்றில் இருந்து விலகி இருங்கள்.",
    },
    "breach": {
        "en": "DAM BREACH confirmed by officer. Move to high ground. {village}: water in {min} minutes.",
        "ta": "அணை உடைப்பு உறுதி. உயரமான இடத்திற்கு செல்லுங்கள். {village}: {min} நிமிடத்தில் நீர் வரும்.",
    },
    "pin_rejected": {
        "en": "Dam-breach command REJECTED: wrong officer PIN. No alert was sent.",
        "ta": "அணை உடைப்பு கட்டளை நிராகரிக்கப்பட்டது: தவறான அதிகாரி PIN. எச்சரிக்கை அனுப்பப்படவில்லை.",
    },
    "tnpcb": {
        "en": "TNPCB notified: high-confidence dye/effluent discharge at {segment} ({label}, {conf}%).",
        "ta": "TNPCB-க்கு தெரிவிக்கப்பட்டது: {segment}-ல் அதிக நம்பகத்தன்மை சாய/கழிவுநீர் வெளியேற்றம் ({label}, {conf}%).",
    },
    "review": {
        "en": "Discharge decision needed: AI saw {label} at {segment} ({conf}%). Officer must decide whether this "
              "is a real dye/effluent discharge from a textile unit before TNPCB is notified.",
        "ta": "வெளியேற்ற முடிவு தேவை: {segment}-ல் AI {label} ஐ கண்டது ({conf}%). TNPCB-க்கு தெரிவிக்கும் முன், "
              "இது ஜவுளி ஆலையின் உண்மையான சாய/கழிவுநீர் வெளியேற்றமா என அதிகாரி முடிவு செய்ய வேண்டும்.",
    },
    "approved": {
        "en": "Officer confirmed a textile/dyeing discharge at {segment} ({label}). TNPCB notified.",
        "ta": "அதிகாரி {segment}-ல் ஜவுளி/சாய கழிவுநீர் வெளியேற்றத்தை உறுதிப்படுத்தினார் ({label}). TNPCB-க்கு தெரிவிக்கப்பட்டது.",
    },
    "dismissed": {
        "en": "Officer ruled out a discharge at {segment} ({label}) — false detection. TNPCB not notified.",
        "ta": "{segment}-ல் வெளியேற்றம் இல்லை என அதிகாரி நிராகரித்தார் ({label}) — தவறான கண்டறிதல். TNPCB-க்கு தெரிவிக்கப்படவில்லை.",
    },
    "low_battery": {
        "en": "Device {station} battery low ({v:.2f} V). Charge or swap the field unit.",
        "ta": "சாதனம் {station} பேட்டரி குறைவு ({v:.2f} V). பேட்டரியை மாற்றுங்கள்.",
    },
    "sensor_fault": {
        "en": "Sensor fault on {station}: level probes disagree ({a:.2f} m vs {b:.2f} m).",
        "ta": "{station} சென்சார் பிழை: அளவீட்டு ப்ரோப்கள் மாறுபடுகின்றன ({a:.2f} மீ vs {b:.2f} மீ).",
    },
    "normal": {
        "en": "No alerts. All stretches Low risk.",
        "ta": "எச்சரிக்கை இல்லை. அனைத்து பகுதிகளும் குறைந்த ஆபத்து.",
    },
}


def pair(key, **params):
    s = STRINGS.get(key)
    if not s:
        return (str(key), str(key))
    try:
        en = s["en"].format(**params)
    except Exception:
        en = s["en"]
    try:
        ta = s["ta"].format(**params)
    except Exception:
        ta = s["ta"]
    return (en, ta)


def one(key, lang="en", **params):
    return pair(key, **params)[0 if lang == "en" else 1]
