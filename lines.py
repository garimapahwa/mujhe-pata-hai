"""Hardcoded line banks per persona. Hindi in Devanagari, English in Latin — never romanized Hindi.

Used for nags (always), cached quick lines, and as the fallback when the LLM is slow/unavailable.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field


@dataclass(frozen=True)
class LineBank:
    nag: dict[int, list[str]]
    welcome_back: list[str]
    excuse_first: list[str]
    excuse_repeat: list[str]
    followup: list[str]  # contains {topic}
    confess: list[str]
    back_to_work: list[str]
    unclear: list[str]
    caught: list[str]  # contains {site}: opening when a distraction is on screen
    busted: list[str]  # contains {site}: excuse contradicted by the screen
    fake_comeback: list[str]  # contains {site}: mouse moved, but the distraction is still focused
    _last: dict[str, str] = field(default_factory=dict, compare=False)

    def pick(self, kind: str, level: int = 1) -> str:
        """Random line, avoiding an immediate repeat of the same one."""
        options: list[str] = self.nag[level] if kind == "nag" else getattr(self, kind)
        key = f"{kind}{level}"
        choices = [o for o in options if o != self._last.get(key)] or options
        line = random.choice(choices)
        self._last[key] = line
        return line


BANKS: dict[str, LineBank] = {
    "mummy": LineBank(
        nag={
            1: [
                "क्या चल रहा है बेटा? Phone चला रही हो? मुझे पता है, मुझे पता है…",
                "बेटा, screen पे कुछ हिल ही नहीं रहा। Phone तो नहीं उठा लिया?",
                "इतनी शांति? ज़रूर reels देख रही हो। मुझे पता है!",
            ],
            2: [
                "बेटा! मैं दूसरी बार बोल रही हूँ। Phone नीचे रखो, अभी!",
                "मैंने इतनी मेहनत से पढ़ाया, और तुम reels देख रही हो? हद है!",
                "शर्मा जी की बेटी को देखो, एक बार भी phone नहीं उठाती। और तुम?",
            ],
            3: [
                "मैं बोल रही हूँ ना! PHONE. नीचे. रखो!",
                "बस! बहुत हो गया! अभी आके phone छीन लूँगी, देख लेना!",
                "हे भगवान! क्या करूँ मैं इस लड़की का? काम करो, अभी के अभी!",
                "चप्पल निकालूँ क्या? Laptop पे वापस आओ, तुरंत!",
            ],
        },
        welcome_back=[
            "आ गई? Good. काम करो।",
            "हाँ, अब ठीक है। चलो, काम करो।",
            "शाबाश! बस, ऐसे ही।",
        ],
        excuse_first=[
            "अच्छा अच्छा… okay.",
            "अच्छा, ठीक है… मान लिया। अभी के लिए।",
            "हम्म… ठीक है बेटा। देखती हूँ।",
        ],
        excuse_repeat=[
            "फिर से बहाना? वाह बेटा, बहाने बनाने में तो पूरी PhD कर ली है!",
            "अच्छा? बिल्कुल वैसे ही, जैसे पिछली बार कर रही थी? हाँ हाँ, सब पता है।",
        ],
        followup=[
            "बेटा, अभी तक {topic} में ही busy हो, या phone में?",
            "{topic}? बहुत लंबा चल गया बेटा। सच बताओ, phone है ना हाथ में?",
        ],
        confess=[
            "चलो, सच तो बोला! वापस काम पे।",
            "सच बोलने के लिए शाबाश। अब phone दूर, और काम शुरू।",
        ],
        back_to_work=[
            "That's my girl! चलो।",
            "ये हुई ना बात! चलो, फटाफट काम करो।",
        ],
        unclear=["क्या? ठीक से बोलो!", "क्या बोला? ज़ोर से बोलो बेटा!"],
        caught=[
            "{site} देख रही हो बेटा? मुझे पता है, मुझे पता है!",
            "अच्छा, तो {site} चल रहा है? पढ़ाई गई तेल लेने!",
        ],
        busted=[
            "पढ़ाई? Screen पे तो {site} चल रहा है! मुझे सब पता है बेटा।",
            "झूठ! {site} खुला है, मैंने अपनी आँखों से देखा। मुझे पता है!",
        ],
        fake_comeback=[
            "Mouse हिलाने से कुछ नहीं होगा बेटा, {site} अभी भी खुला है!",
            "Scroll करना काम नहीं होता बेटा! {site} बंद करो, अभी!",
        ],
    ),
    "dost": LineBank(
        nag={
            1: [
                "Bro… seriously? Reels? मुझे पता है, मुझे पता है।",
                "ओए, screen पे कुछ हिल नहीं रहा। Phone scroll चल रहा है ना?",
                "Scene क्या है? Laptop को ghost कर दिया?",
            ],
            2: [
                "Bro, literally दूसरी बार बोल रही हूँ। Phone side में रख!",
                "यार, ये reels तुझे job नहीं देंगी। No cap.",
                "Deadline रो रही है bro, और तू memes देख रही है।",
            ],
            3: [
                "BRO. PHONE. नीचे. रख! अभी के अभी!",
                "बस! मैं तेरी mom को call कर रही हूँ। Seriously!",
                "Okay, ये अब intervention है! Laptop पे वापस आ, NOW!",
            ],
        },
        welcome_back=[
            "आ गई? Good. काम कर।",
            "Ayy, welcome back! Focus mode on.",
            "Okay okay, अब ठीक है। Grind कर।",
        ],
        excuse_first=[
            "अच्छा अच्छा… okay bro.",
            "Hmm… sure, sure. मान लिया।",
            "Okay… trust issues हैं, पर ठीक है।",
        ],
        excuse_repeat=[
            "फिर से? Bro, तेरे बहानों की तो Netflix series बन सकती है।",
            "Wow, excuse number two. Creative है तू, मानना पड़ेगा।",
        ],
        followup=[
            "Bro, अभी तक {topic} में busy है, या reels में?",
            "{topic} का scene अभी भी चल रहा है? Sus लग रहा है bro।",
        ],
        confess=[
            "Respect bro, सच बोला! अब वापस काम पे।",
            "Honesty के लिए ten points। अब phone दूर।",
        ],
        back_to_work=["That's my girl! चल।", "Let's go! Main character energy!"],
        unclear=["क्या? ठीक से बोल!", "Bro, कुछ समझ नहीं आया। फिर से बोल!"],
        caught=[
            "Bro, {site}? Seriously? मुझे पता है!",
            "{site} खुला है और तू बोलेगी काम कर रही थी? Caught!",
        ],
        busted=[
            "Bro, {site} खुला है। Nice try! मुझे पता है।",
            "Excuse मत दे, screen पे {site} है। Caught in 4K!",
        ],
        fake_comeback=[
            "Bro, mouse हिलाने को काम नहीं कहते। {site} बंद कर!",
            "Nice try bro, {site} पे scroll करना productivity नहीं है!",
        ],
    ),
    "commentator": LineBank(
        nag={
            1: [
                "और ये गई focus boundary के पार! Phone ने एक और wicket लिया!",
                "Ladies and gentlemen, laptop पे कोई movement नहीं! क्या ये phone की तरफ़ जा रही हैं?",
                "Keyboard बिल्कुल शांत है, दर्शकों! कुछ तो गड़बड़ है!",
            ],
            2: [
                "और ये दूसरी बार! Productivity का run rate गिरता जा रहा है!",
                "Third umpire review कर रहे हैं, और replay में साफ़ दिख रहा है, phone हाथ में है!",
                "क्या shot है, सीधा reels के stadium में!",
            ],
            3: [
                "OUT! OUT! OUT! पूरा stadium खड़ा हो गया है! PHONE. नीचे. रखो!",
                "ये तो match हाथ से निकल रहा है! Captain, कुछ कीजिए!",
                "ऐसा collapse मैंने अपने career में नहीं देखा! वापस आओ, crease पर!",
            ],
        },
        welcome_back=[
            "और वो वापस crease पर! Good. खेलते रहो!",
            "Comeback of the season! Keyboard फिर से चालू!",
            "क्या return है! Crowd तालियाँ बजा रहा है!",
        ],
        excuse_first=[
            "अच्छा अच्छा… umpire ने benefit of the doubt दिया है।",
            "Hmm, DRS pending है। अभी के लिए not out।",
        ],
        excuse_repeat=[
            "दूसरा excuse! Umpire अब बिल्कुल convinced नहीं हैं!",
            "ये बहाना तो no ball है, साफ़ साफ़!",
        ],
        followup=[
            "और हम वापस live! क्या अभी तक {topic} में busy हैं, या phone का spell चल रहा है?",
            "Replay देखते हैं। दावा था {topic} का… पर camera तो phone दिखा रहा है!",
        ],
        confess=[
            "सच की जीत! Fair play award इन्हें जाता है। अब वापस batting पे!",
            "Honest confession! Crowd खड़ा होके तालियाँ बजा रहा है। चलो, काम!",
        ],
        back_to_work=["That's my girl! क्या comeback है!", "और ये वापस form में! Century पक्की!"],
        unclear=["क्या? Stadium में शोर बहुत है, ठीक से बोलो!", "Mic में आवाज़ नहीं आई! फिर से बोलिए!"],
        caught=[
            "और camera ने पकड़ लिया, screen पे {site} चल रहा है! क्या drama है!",
            "{site} के stadium से live! Focus तो boundary के पार!",
        ],
        busted=[
            "Third umpire ने replay देखा, screen पे {site}! ये तो साफ़ झूठ है!",
            "DRS ले लिया! Ball tracking कहती है {site}! OUT!",
        ],
        fake_comeback=[
            "Fake movement! Mouse चला, पर screen पे अभी भी {site}! Umpire convinced नहीं हैं!",
            "Batting का नाटक! {site} पे scroll चल रहा है, दर्शकों!",
        ],
    ),
    "filmy": LineBank(
        nag={
            1: [
                "देवियों और सज्जनों… keyboard ख़ामोश है। और हम जानते हैं, इस ख़ामोशी के पीछे, phone है।",
                "हम सब देख रहे हैं… ये laptop अकेला इंतज़ार कर रहा है। मुझे पता है।",
                "कहानी में एक मोड़ आया है… heroine ने काम छोड़ा, और phone उठा लिया।",
            ],
            2: [
                "हमने कहा था… deadline किसी का इंतज़ार नहीं करती। और आप, reels का इंतज़ार कर रही हैं?",
                "ये pending tasks की list… हमसे पूछ रही है, इसका गुनहगार कौन है?",
                "हम दूसरी बार कह रहे हैं… phone रख दीजिए। तीसरी बार, कहानी बदल जाएगी।",
            ],
            3: [
                "बस! बहुत हुआ! आज हम फ़ैसला सुनाएँगे… PHONE. नीचे. रखिए!",
                "इतिहास गवाह है… जिसने deadline को नज़रअंदाज़ किया, वो पछताया है! काम पे लौटिए!",
                "ये आख़िरी चेतावनी है… laptop खोलिए, वरना ये कहानी, tragedy बन जाएगी!",
            ],
        },
        welcome_back=[
            "आ गईं? बहुत ख़ूब। कहानी फिर से पटरी पर है।",
            "यही है असली हीरो की पहचान… वापसी। काम कीजिए।",
            "शाबाश… अब परदा उठता है, काम का।",
        ],
        excuse_first=["अच्छा अच्छा… ठीक है।", "अच्छा अच्छा… हम मान लेते हैं। फ़िलहाल।"],
        excuse_repeat=[
            "फिर वही बहाना? ये कहानी, हम पहले भी सुन चुके हैं।",
            "बहाने बदल गए, पर phone वही है… हम सब समझते हैं।",
        ],
        followup=[
            "हम लौट आए हैं… क्या अभी तक {topic} में ही busy हैं, या phone में?",
            "{topic}… बड़ा लंबा चला। हमें सच सुनना है, phone हाथ में है ना?",
        ],
        confess=[
            "सच कहने के लिए, हिम्मत चाहिए… और आपने दिखा दी। अब काम।",
            "सच की हमेशा जीत होती है… चलिए, वापस काम पर।",
        ],
        back_to_work=["That's my girl! अब होगी असली शुरुआत।", "ये हुई ना हीरो वाली बात! चलिए।"],
        unclear=["क्या कहा? ज़रा साफ़ बोलिए।", "आवाज़ नहीं पहुँची… फिर से कहिए।"],
        caught=[
            "देवियों और सज्जनों… screen पर {site} चल रहा है। और हम, सब जानते हैं।",
            "कहानी में twist… काम की जगह, {site}!",
        ],
        busted=[
            "पढ़ाई? परदे पर तो {site} चल रहा है! हमसे झूठ? नामुमकिन।",
            "झूठ के पैर नहीं होते… और screen पर {site} है।",
        ],
        fake_comeback=[
            "Mouse हिलाने से कहानी नहीं बदलती… {site} अभी भी खुला है।",
            "ये नाटक हम पहचानते हैं… {site} बंद कीजिए।",
        ],
    ),
    "action": LineBank(
        nag={
            1: [
                "ओए! Keyboard चुप क्यों है? Phone उठाया ना? मुझे पता है!",
                "ये सन्नाटा मुझे पसंद नहीं! काम पे वापस आओ!",
                "Laptop बुला रहा है, और तुम गायब? नहीं चलेगा!",
            ],
            2: [
                "दूसरी बार बोल रहा हूँ! Phone नीचे! अभी!",
                "ये deadline कोई मज़ाक नहीं है! उठो, और काम करो!",
                "मेरी आवाज़ ऊँची हो रही है! समझ जाओ, वक़्त कम है!",
            ],
            3: [
                "बस! अब मैं table तोड़ दूँगा! PHONE. नीचे. रखो!",
                "आर या पार! या तो काम, या फिर मेरा गुस्सा!",
                "ये आख़िरी warning है! Laptop पे वापस आओ, तुरंत!",
            ],
        },
        welcome_back=[
            "आ गई? Good! अब रुकना नहीं!",
            "यही चाहिए था! Full power से काम करो!",
            "शाबाश! ये हुई ना fighter वाली बात!",
        ],
        excuse_first=["अच्छा अच्छा… ठीक है।", "अच्छा अच्छा… देखते हैं!"],
        excuse_repeat=["फिर बहाना? मेरा सब्र मत आज़माओ!", "बहाने पे बहाना! अब बस!"],
        followup=[
            "मैं वापस आ गया! अभी तक {topic} में busy हो, या phone में?",
            "{topic}? इतनी देर? सच बोलो, phone हाथ में है ना!",
        ],
        confess=["सच बोला! Respect! अब वापस काम पे!", "ये हुई ना हिम्मत! चलो, काम शुरू!"],
        back_to_work=["That's my girl! चलो, धमाका करो!", "ये हुई ना बात! Full speed!"],
        unclear=["क्या? ज़ोर से बोलो!", "सुनाई नहीं दिया! फिर से!"],
        caught=["Screen पे {site}? मुझे पता है! बंद करो इसे!", "पकड़ी गई! {site} चल रहा है! काम कहाँ है?"],
        busted=["पढ़ाई? Screen पे {site} है! झूठ नहीं चलेगा!", "झूठ! {site} खुला है! मैं सब देख रहा हूँ!"],
        fake_comeback=["Mouse हिलाने से कुछ नहीं होगा! {site} बंद करो!", "ये नाटक बंद करो! {site} अभी भी खुला है!"],
    ),
}

AUDITION_LINE = "क्या चल रहा है? Phone चला रही हो? मुझे पता है, मुझे पता है… चलो, वापस काम पे!"


def excuse_topic(excuse: str) -> str:
    """Short Hinglish noun phrase for the user's last excuse, for follow-up templates."""
    t = excuse.lower()
    if any(k in t for k in ("meeting", "मीटिंग")):
        return "वो meeting"
    if any(k in t for k in ("call", "कॉल", "फ़ोन पे बात", "फोन पे बात")):
        return "वो call"
    if any(k in t for k in ("read", "padh", "पढ़", "पढ", "article", "book", "किताब", "रीड")):
        return "वो reading"
    if any(k in t for k in ("soch", "सोच", "think")):
        return "वो सोचना"
    return "वो ज़रूरी काम"


def all_quick_lines(persona: str) -> list[str]:
    bank = BANKS[persona]
    return bank.nag[1] + bank.welcome_back
