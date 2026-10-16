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
    "papa": LineBank(
        nag={
            1: [
                "हम्म। Keyboard बंद है। Phone चल रहा है ना? मुझे पता है।",
                "बेटा, इतनी शांति क्यों है? काम हो रहा है, या सिर्फ़ बिजली का bill बढ़ रहा है?",
                "मैं कुछ नहीं कहूँगा। बस इतना, मुझे पता है।",
            ],
            2: [
                "दूसरी बार बोल रहा हूँ। Phone रखो, और काम पे ध्यान दो।",
                "हमारे ज़माने में phone नहीं था, फिर भी हमने पढ़ाई की। और तुम?",
                "बेटा, career ऐसे नहीं बनता। Phone नीचे।",
            ],
            3: [
                "बस! अब मैं wifi का password बदल दूँगा!",
                "मुझे ग़ुस्सा मत दिलाओ। PHONE. नीचे. रखो!",
                "आज खाने पे बात होगी। अभी, काम करो!",
            ],
        },
        welcome_back=["ठीक है। काम करो।", "हम्म। Good.", "हाँ, अब सही है।"],
        excuse_first=["अच्छा… ठीक है।", "हम्म… देखते हैं।"],
        excuse_repeat=["फिर वही बहाना? बेटा, मैं भी कभी जवान था।", "हर बार नया बहाना। Career का क्या होगा?"],
        followup=["अभी तक {topic} ही चल रहा है, या phone?", "{topic}? इतनी देर? सच बताओ बेटा।"],
        confess=["सच बोला, अच्छा लगा। अब काम करो।", "ठीक है। ईमानदारी की क़द्र है। चलो, काम।"],
        back_to_work=["That's my girl. चलो।", "शाबाश बेटा। ऐसे ही।"],
        unclear=["क्या? साफ़ बोलो।", "हम्म? फिर से बोलो।"],
        caught=["{site}? बेटा, मुझे पता है।", "तो {site} चल रहा है। Fees मैं भर रहा हूँ, याद है?"],
        busted=["काम? Screen पे तो {site} है। झूठ मत बोलो बेटा।", "झूठ। {site} खुला है। मुझे सब पता है।"],
        fake_comeback=["Mouse हिलाने से काम नहीं होता बेटा। {site} बंद करो।", "{site} अभी भी खुला है। ये नाटक बंद करो।"],
    ),
    "dadi": LineBank(
        nag={
            1: [
                "अरे मेरी लाडो, phone में आँखें ख़राब हो जाएँगी। मुझे पता है, मुझे पता है।",
                "बिटिया, कुछ लिख नहीं रही? Phone तो नहीं ले लिया?",
                "इतनी चुप्पी? ज़रूर वो reels देख रही है। मुझे पता है!",
            ],
            2: [
                "हाय राम! फिर से phone? दादी की बात नहीं मानेगी?",
                "हमारे ज़माने में तो लालटेन में पढ़ते थे, और तुम phone में घुसी हो!",
                "बिटिया, phone रख दे। दादी के लिए। अच्छा?",
            ],
            3: [
                "हे भगवान! इस लड़की का क्या होगा! Phone रख, अभी!",
                "अब तो मैं तेरी मम्मी को बता दूँगी! काम कर, जल्दी!",
                "बस कर! मेरा BP बढ़ जाएगा! Laptop पे वापस आ!",
            ],
        },
        welcome_back=["शाबाश मेरी लाडो!", "हाँ, ऐसे ही। जीती रह!", "आ गई? बहुत अच्छे।"],
        excuse_first=["अच्छा अच्छा… ठीक है बिटिया।", "हम्म… मान लिया।"],
        excuse_repeat=["फिर से बहाना? दादी को बुद्धू समझा है क्या?", "ये बहाना तो मैं तेरे पापा से भी सुन चुकी हूँ!"],
        followup=["बिटिया, अभी तक {topic} ही है, या phone?", "{topic}? इतनी देर? सच बता दादी को।"],
        confess=["सच बोला, मेरी प्यारी। अब काम कर।", "शाबाश, सच बोलने वाले की हमेशा जीत होती है। चल, काम।"],
        back_to_work=["That's my girl! जीती रह।", "ये हुई ना बात! दादी को तुझ पे गर्व है।"],
        unclear=["क्या बोली? दादी को ठीक से सुनाई नहीं दिया!", "ज़ोर से बोल बिटिया!"],
        caught=["{site} देख रही है? मुझे पता है, मुझे पता है!", "अरे, ये {site} क्या चल रहा है? पढ़ाई कहाँ है?"],
        busted=["काम? Screen पे तो {site} है! दादी से झूठ?", "झूठ! {site} खुला है। इन बूढ़ी आँखों ने देख लिया!"],
        fake_comeback=["Mouse हिलाने से दादी नहीं मानेगी! {site} बंद कर!", "{site} अभी भी खुला है बिटिया। बंद कर।"],
    ),
    "didi": LineBank(
        nag={
            1: [
                "Excuse me? Phone? मुझे पता है, मुझे पता है।",
                "Typing की आवाज़ बंद है। Reels चालू हैं ना?",
                "Hello? काम कौन करेगा? मैं?",
            ],
            2: [
                "दूसरी बार बोल रही हूँ। Phone रख, वरना मम्मी को बताती हूँ।",
                "मैंने तेरी उम्र में इतना phone नहीं चलाया था, seriously।",
                "Screenshot ले लिया है। Proof मेरे पास है।",
            ],
            3: [
                "मम्मी! देखो इसे! फिर से phone!",
                "बस! तेरा charger मैं ले जा रही हूँ!",
                "Last warning! PHONE. नीचे. रख!",
            ],
        },
        welcome_back=["Good. अब रुकना मत।", "हाँ, ऐसे। Proud of you, थोड़ा सा।", "आ गई? Fine."],
        excuse_first=["अच्छा अच्छा… okay.", "Hmm… चल, मान लिया।"],
        excuse_repeat=["ये बहाना मैंने ही invent किया था। मुझसे नहीं चलेगा।", "फिर से? Creativity कम हो गई है तेरी।"],
        followup=["अभी तक {topic} में ही है, या phone में?", "{topic}? इतनी देर? मम्मी को call करूँ?"],
        confess=["सच बोला, respect। अब काम कर।", "Okay, honesty के points। चल, काम।"],
        back_to_work=["That's my girl! चल।", "ये हुई ना बात! मम्मी को नहीं बताऊँगी।"],
        unclear=["क्या? Clearly बोल।", "Hello? सुनाई नहीं दिया।"],
        caught=["{site}? Seriously? मुझे पता है!", "तो {site} चल रहा है। मम्मी को बताऊँ?"],
        busted=["पढ़ाई? Screen पे {site} है। Nice try।", "झूठ! {site} खुला है। Screenshot ले लिया।"],
        fake_comeback=["Mouse हिलाना काम नहीं है। {site} बंद कर।", "{site} अभी भी खुला है, smart girl।"],
    ),
    "boss": LineBank(
        nag={
            1: [
                "Hi, quick sync? Keyboard पे कोई activity नहीं दिख रही। मुझे पता है।",
                "बस check कर रहा था, deliverables का status क्या है? Phone तो नहीं?",
                "Just a gentle reminder, EOD deadline है। मुझे पता है, मुझे पता है।",
            ],
            2: [
                "Second reminder. Phone रखो, priorities align करो।",
                "आपकी bandwidth phone में जा रही है, task में नहीं।",
                "इसको appraisal में note कर लूँ?",
            ],
            3: [
                "ये escalation है! PHONE. नीचे. रखो!",
                "अभी के अभी एक meeting बुला रहा हूँ! काम पे वापस!",
                "No more excuses! Deadline आज है, अभी!",
            ],
        },
        welcome_back=["Great, let's keep the momentum.", "Perfect, अब progress दिख रहा है।", "Good. Keep it up."],
        excuse_first=["अच्छा अच्छा… noted.", "Okay… let's circle back on this."],
        excuse_repeat=["Same excuse, second time। ये pattern है।", "फिर से? इसका भी root cause analysis करना पड़ेगा।"],
        followup=["{topic} का update? या phone का?", "{topic} अभी तक? Timeline बताओ।"],
        confess=["Thanks for the transparency। अब काम पे।", "Honesty appreciated। चलो, deliver करते हैं।"],
        back_to_work=["That's the spirit! चलो।", "Great, let's ship it!"],
        unclear=["Sorry, you're on mute? फिर से बोलो।", "Connection ख़राब है? साफ़ बोलो।"],
        caught=["{site}? Work hours में? मुझे पता है।", "मैं देख रहा हूँ, {site} खुला है। Productive?"],
        busted=["काम? Screen पे {site} है। Let's be honest।", "झूठ! {site} खुला है। ये HR तक जाएगा।"],
        fake_comeback=["Mouse हिलाना productivity नहीं है। {site} बंद करो।", "{site} अभी भी open है। Focus, please।"],
    ),
    "teacher": LineBank(
        nag={
            1: [
                "Last bench! हाँ, आप ही। Phone चला रही हो? मुझे पता है।",
                "Class में इतनी शांति? कोई कुछ लिख नहीं रहा।",
                "मैं board पे लिख रही हूँ, और आपका ध्यान phone में। मुझे पता है!",
            ],
            2: [
                "दूसरी बार बोल रही हूँ। Phone मेरे desk पे रखो।",
                "Homework पूरा हुआ? नहीं ना? तो phone क्यों?",
                "Diary में note लिख दूँ? Parents sign करेंगे।",
            ],
            3: [
                "Get out of my class! नहीं, रुको, पहले काम करो!",
                "Parents को बुलाना पड़ेगा! PHONE. नीचे. रखो!",
                "Principal के office चलें? काम करो, अभी!",
            ],
        },
        welcome_back=["Very good! ऐसे ही।", "शाबाश, ये होती है अच्छी student।", "Good. Concentrate."],
        excuse_first=["अच्छा अच्छा… sit down।", "Hmm… ठीक है, इस बार।"],
        excuse_repeat=["ये बहाना पिछले हफ़्ते भी सुना था।", "कुत्ता homework खा गया? हर बार?"],
        followup=["अभी तक {topic} ही चल रहा है?", "{topic}? इतनी देर? Show me your copy।"],
        confess=["सच बोला, उसके marks मिलेंगे। अब काम।", "Good, honesty important है। चलो, काम करो।"],
        back_to_work=["That's my girl! Very good।", "ये हुई ना बात! Gold star।"],
        unclear=["क्या? खड़े होके बोलो।", "ज़ोर से बोलो, पूरी class सुने।"],
        caught=["{site}? Class में? मुझे पता है!", "{site} चल रहा है? ये syllabus में नहीं है!"],
        busted=["पढ़ाई? Screen पे {site} है। झूठ बोलना बुरी बात है।", "झूठ! {site} खुला है। Diary लाओ।"],
        fake_comeback=["Mouse हिलाने से homework नहीं होता! {site} बंद करो।", "{site} अभी भी खुला है। मैं देख रही हूँ।"],
    ),
    "news": LineBank(
        nag={
            1: [
                "Breaking news! Keyboard पिछले कई seconds से ख़ामोश। सूत्रों के मुताबिक, phone हाथ में है।",
                "आप देख रहे हैं Focus Live। Laptop पर सन्नाटा, और सवाल वही, phone?",
                "ताज़ा ख़बर! काम रुका हुआ है। मुझे पता है, मुझे पता है।",
            ],
            2: [
                "बड़ी ख़बर! दूसरी चेतावनी भी नज़रअंदाज़! देश जानना चाहता है, phone क्यों?",
                "हमारे संवाददाता बता रहे हैं, reels का सिलसिला जारी है!",
                "Deadline नज़दीक, और हालात चिंताजनक!",
            ],
            3: [
                "सबसे बड़ा खुलासा! PHONE. नीचे. रखो!",
                "ये ख़बर हर channel पर! काम पे वापस आओ, अभी!",
                "अभी-अभी! ये आख़िरी चेतावनी है! Laptop पर लौटो!",
            ],
        },
        welcome_back=["Update: काम दोबारा शुरू! राहत की ख़बर!", "ख़बर पक्की, user वापस आ गई!", "हालात सामान्य, काम जारी।"],
        excuse_first=["अच्छा अच्छा… हम इस दावे की जाँच करेंगे।", "ठीक है… fact check जारी है।"],
        excuse_repeat=["वही पुराना बयान! जनता सब समझती है!", "दोबारा बहाना! ये ख़बर कल के अख़बार में होगी!"],
        followup=["Update चाहिए, {topic} अभी भी जारी है?", "{topic}? इतनी देर? सूत्र कुछ और कहते हैं।"],
        confess=["Exclusive क़बूलनामा! अब काम पे वापसी।", "सच सामने आया! चलो, काम।"],
        back_to_work=["That's my girl! ये रही आज की सबसे अच्छी ख़बर!", "बड़ी ख़बर, user ने काम शुरू किया!"],
        unclear=["Signal कमज़ोर है! फिर से बोलिए!", "आवाज़ साफ़ नहीं आ रही! दोबारा!"],
        caught=["Breaking! Screen पर {site} देखा गया! मुझे पता है!", "Exclusive तस्वीरें, {site} खुला है!"],
        busted=["दावा झूठा! Screen पर {site} चल रहा है!", "Fact check, झूठ! {site} खुला है!"],
        fake_comeback=["Mouse हिला, पर {site} अभी भी खुला है! ख़बर जारी!", "Update, {site} अभी तक बंद नहीं हुआ!"],
    ),
    "detective": LineBank(
        nag={
            1: [
                "सन्नाटा… keyboard ख़ामोश… और एक phone, जो अभी भी गर्म है। मुझे पता है।",
                "Case number एक… laptop अकेला पड़ा है। Suspect कहाँ है?",
                "हर सबूत एक ही तरफ़ इशारा कर रहा है… reels।",
            ],
            2: [
                "दूसरा सुराग… phone की screen अभी भी जल रही है।",
                "Suspect अभी भी गायब है… और deadline क़रीब आ रही है।",
                "मैं सब नोट कर रहा हूँ… हर एक minute।",
            ],
            3: [
                "Case solved! PHONE. नीचे. रखो!",
                "अब कोई बच नहीं सकता! Laptop पे वापस, अभी!",
                "आख़िरी सबूत मिल गया! काम करो, तुरंत!",
            ],
        },
        welcome_back=["Suspect वापस मिल गई… case closed।", "हम्म… काम दोबारा शुरू। अच्छा।", "लौट आई… अच्छा फ़ैसला।"],
        excuse_first=["अच्छा अच्छा… alibi नोट कर लिया।", "हम्म… देखते हैं ये कहानी कहाँ तक जाती है।"],
        excuse_repeat=["वही alibi, दोबारा… दिलचस्प।", "कहानी में छेद है… बहुत बड़ा।"],
        followup=["{topic}… अभी तक? या phone?", "{topic}… इतनी देर? सबूत कुछ और कहते हैं।"],
        confess=["क़बूलनामा… case closed। अब काम।", "सच… आख़िरकार। चलो, काम।"],
        back_to_work=["That's my girl… mystery solved।", "ये हुई ना बात… case closed।"],
        unclear=["क्या? साफ़ बोलो… हर शब्द सबूत है।", "फिर से बोलो… धीरे।"],
        caught=["Screen पर… {site}। मुझे पता है।", "सबूत मिल गया… {site} खुला है।"],
        busted=["Alibi झूठा है… screen पर {site} है।", "झूठ… {site} खुला है। Case closed।"],
        fake_comeback=["Mouse हिलाने से सबूत नहीं मिटता… {site} अभी भी खुला है।", "{site}… अभी भी वहीं है। मैं देख रहा हूँ।"],
    ),
    # --- Bollywood: famous film dialogues twisted into scoldings. Bulbul voices; never an actor's voice or name.
    "angry": LineBank(
        nag={
            1: [
                "आज मेरे पास laptop है, deadline है, assignment है… तुम्हारे पास क्या है? Reels?",
                "Deadline को पकड़ना मुश्किल ही नहीं… नामुमकिन है। और तुम phone पकड़े बैठी हो।",
                "रिश्ते में तो हम तुम्हारी deadline लगते हैं… नाम है, submission। मुझे पता है।",
            ],
            2: [
                "मैं आज भी फेंके हुए phone नहीं उठाता… पर तुम्हारा phone, मैं ख़ुद फेंक दूँगा।",
                "Keyboard ख़ामोश है… और ये ख़ामोशी, तूफ़ान से पहले की है।",
                "जहाँ हम खड़े होते हैं… deadline वहीं से शुरू होती है। Phone नीचे।",
            ],
            3: [
                "ये work desk है, कोई Netflix का theatre नहीं! PHONE. नीचे. रखो!",
                "नालायक! आज फ़ैसला होगा, काम या phone! Laptop पे वापस, अभी!",
                "बस! मेरा सब्र जवाब दे चुका है! काम करो, तुरंत!",
            ],
        },
        welcome_back=["आ गई? ठीक है। अब रुकना नहीं।", "हम्म… यही होना चाहिए था।", "अच्छा। अब जीत तुम्हारी है।"],
        excuse_first=["अच्छा अच्छा… देखते हैं।", "अच्छा अच्छा… ठीक है।"],
        excuse_repeat=["फिर वही बहाना? मेरी आँखों में देखो… झूठ।", "बहाने कमज़ोर लोग बनाते हैं।"],
        followup=["{topic}… अभी तक? या phone?", "{topic}… इतनी देर? मुझसे कुछ छुपता नहीं।"],
        confess=["सच बोला… हिम्मत है। अब काम।", "ये हुई ना बात। सच के आगे सब छोटा है। चलो, काम।"],
        back_to_work=["That's my girl… अब कोई नहीं रोक सकता।", "ये हुई ना बात। अब जीतेंगे।"],
        unclear=["क्या? साफ़ बोलो।", "आवाज़ में दम नहीं है। फिर से।"],
        caught=["Screen पर… {site}। मुझे पता है।", "{site}? काम के वक़्त? ये बर्दाश्त नहीं होगा।"],
        busted=["झूठ… screen पर {site} है।", "पढ़ाई? {site} खुला है। मेरी आँखों से कुछ नहीं छुपता।"],
        fake_comeback=["Mouse हिलाने से कुछ नहीं बदलता… {site} अभी भी खुला है।", "ये चालाकी मुझ पर नहीं चलेगी। {site} बंद करो।"],
    ),
    "romantic": LineBank(
        nag={
            1: [
                "बड़े-बड़े शहरों में, ऐसी छोटी-छोटी reels चलती रहती हैं… पर deadline, एक ही होती है।",
                "Deadline… नाम तो सुना होगा? वो तुम्हारा इंतज़ार कर रही है।",
                "अगर किसी assignment को दिल से चाहो… तो पूरी कायनात उसे complete करवाने में लग जाती है। Phone छोड़ो।",
            ],
            2: [
                "पलट… पलट… laptop की तरफ़ पलट!",
                "जा… जी ले अपनी ज़िंदगी। पर पहले, assignment submit कर।",
                "कुछ कुछ होता है… जब तुम phone उठाती हो। और वो अच्छा नहीं होता।",
            ],
            3: [
                "बस! ये प्यार नहीं, reels की लत है! PHONE. नीचे. रखो!",
                "मेरा दिल टूट रहा है! Deadline जा रही है, laptop पे आओ!",
                "अब और नहीं! पलट, और काम कर, अभी!",
            ],
        },
        welcome_back=["आ गई… मुझे पता था, तुम लौटोगी।", "ये मिलन… कितना ख़ूबसूरत है। काम करो।", "हाँ… अब कहानी पूरी होगी।"],
        excuse_first=["अच्छा अच्छा… मान लिया।", "अच्छा अच्छा… तुम कहती हो, तो ठीक है।"],
        excuse_repeat=["फिर वही बहाना? दिल ने इस बार नहीं माना।", "बहाने… प्यार में नहीं चलते।"],
        followup=["{topic}… अभी तक? या फिर वही phone?", "{topic}… इतना लंबा? सच बताओ, phone है ना?"],
        confess=["सच बोला… इसी ईमानदारी पे तो दिल आया था। अब काम।", "सच… सबसे ख़ूबसूरत चीज़। चलो, काम करो।"],
        back_to_work=["That's my girl… अब ये कहानी hit होगी।", "ये हुई ना बात! चलो, climax की तरफ़।"],
        unclear=["क्या? दिल की बात साफ़ बोलो।", "फिर से कहो… धीरे से।"],
        caught=["{site}… और मैं सोच रहा था, तुम काम कर रही हो। मुझे पता है।", "तुम्हारी screen पर… {site}। दिल टूट गया।"],
        busted=["पढ़ाई? Screen पर तो {site} है… ये धोखा है।", "झूठ… {site} खुला है। इतनी बेवफ़ाई?"],
        fake_comeback=["Mouse हिलाने से प्यार साबित नहीं होता… {site} बंद करो।", "{site} अभी भी खुला है… मुझसे नज़रें मत चुराओ।"],
    ),
    "bhai": LineBank(
        nag={
            1: [
                "एक बार जो मैंने commitment कर दी… उसके बाद मैं phone की भी नहीं सुनता। तू क्यों सुन रही है?",
                "थप्पड़ से डर नहीं लगता साहब… deadline से लगता है। और तुझे? Reels से प्यार है।",
                "देख। Keyboard बंद। Phone चालू। मुझे पता है।",
            ],
            2: [
                "मुझ पर एक एहसान करना… कि मुझ पर कोई एहसान मत करना। बस phone नीचे रख।",
                "Control, पगले, control! Phone को हाथ मत लगा।",
                "दूसरी बार बोल रहा हूँ। Phone नीचे। समझा?",
            ],
            3: [
                "बस! अब भाई को ग़ुस्सा आ गया! PHONE. नीचे!",
                "नालायक! स्वागत नहीं करेगी laptop का? अभी के अभी वापस!",
                "अब बात नहीं, सीधा action होगा! काम कर!",
            ],
        },
        welcome_back=["आ गई? शाबाश। रुकना मत।", "ये हुई ना बात। भाई खुश।", "Good. अब full power।"],
        excuse_first=["अच्छा अच्छा… चल, मान लिया।", "अच्छा अच्छा… ठीक है।"],
        excuse_repeat=["फिर वही? भाई को बेवकूफ़ समझा है?", "बहाना नंबर दो। भाई गिन रहा है।"],
        followup=["{topic} अभी तक? या phone? सच बोल।", "{topic}? इतनी देर? भाई सब जानता है।"],
        confess=["सच बोला। Respect। अब काम।", "दिल जीत लिया। चल, काम पे।"],
        back_to_work=["That's my girl! चल, धमाका कर।", "ये हुई ना बात! भाई proud है।"],
        unclear=["क्या? ठीक से बोल।", "सुनाई नहीं दिया। फिर से।"],
        caught=["{site}? देख, मुझे पता है।", "पकड़ी गई। {site} चल रहा है।"],
        busted=["पढ़ाई? Screen पे {site} है। भाई से झूठ?", "झूठ! {site} खुला है। समझा?"],
        fake_comeback=["Mouse हिलाने से कुछ नहीं होगा। {site} बंद कर।", "भाई को चलाकी मत दिखा। {site} अभी भी खुला है।"],
    ),
    "villain": LineBank(
        nag={
            1: [
                "Mogambo ख़ुश हुआ! Keyboard बंद, phone चालू। हा हा हा!",
                "कितने tabs थे? पूरे बीस? और काम का एक भी नहीं? हा हा हा!",
                "अरे ओ सांभा… कितना syllabus बाकी है? पूरा? हा हा हा, बहुत ख़ूब!",
            ],
            2: [
                "जो phone पे गया… समझो deadline से गया। हा हा हा!",
                "उठा ले रे बाबा, उठा ले… मुझे नहीं, ये phone उठा ले!",
                "मूर्ख! हर minute, deadline और ताक़तवर हो रही है!",
            ],
            3: [
                "हा हा हा! अब तुम्हें कोई नहीं बचा सकता! PHONE. नीचे. रखो!",
                "ये phone हमको दे दे! Laptop पे वापस आओ, अगर हिम्मत है!",
                "नालायक! आख़िरी मौका! काम करो, वरना Mogambo जीत जाएगा!",
            ],
        },
        welcome_back=["Mogambo दुखी हुआ… तुम वापस आ गई।", "क्या? तुम वापस आ गई? ये नहीं हो सकता!", "उफ़्फ़… मेरा plan फ़ेल हो गया।", "हम्म… इस बार तुम जीत गई।"],
        excuse_first=["अच्छा अच्छा… हा हा हा, देखते हैं।", "अच्छा अच्छा… ठीक है।"],
        excuse_repeat=["फिर वही बहाना? हा हा हा, मुझे और मज़ा आ रहा है!", "बहाने पे बहाना… मेरी जीत क़रीब है!"],
        followup=["{topic}… अभी तक? हा हा हा, या फिर phone?", "{topic}? इतनी देर? मेरा plan चल रहा है।"],
        confess=["क्या? सच बोल दिया? मेरा plan बर्बाद! चलो, काम करो।", "सच… मेरा सबसे बड़ा दुश्मन। अब काम।"],
        back_to_work=["That's my girl? नहीं! मेरी हार हो गई!", "ये नहीं हो सकता… तुम काम करने लगी!"],
        unclear=["क्या? ज़ोर से बोलो, मूर्ख!", "हा? फिर से बोलो!"],
        caught=["हा हा हा… screen पर {site}। मुझे पता है!", "{site}! बहुत ख़ूब… मेरा plan कामयाब।"],
        busted=["पढ़ाई? हा हा हा, screen पर तो {site} है!", "झूठ! {site} खुला है। मैं सब देख रहा हूँ।"],
        fake_comeback=["Mouse हिलाओ, हा हा हा… {site} तो अभी भी खुला है!", "ये चाल पुरानी है। {site} अभी भी वहीं है।"],
    ),
    "coach": LineBank(
        nag={
            1: [
                "सत्तर minute हैं तुम्हारे पास… शायद ज़िंदगी के सबसे ख़ास सत्तर minute। Phone रखो।",
                "काबिल बनो, काबिल। Marks झक मार के पीछे आएँगे। पर reels से नहीं।",
                "Oye! Crease छोड़ के कहाँ गई? Phone? मुझे पता है।",
            ],
            2: [
                "मुझे states के नाम नहीं सुनने… मुझे सिर्फ़ एक नाम सुनना है, assignment!",
                "ये तो आसान catch था, और तुमने छोड़ दिया! फोकस!",
                "दूसरी warning! Phone dressing room में छोड़ के आओ!",
            ],
            3: [
                "Bat का grip निकालूँ क्या? Crease पे वापस आओ!",
                "Final over चल रहा है! PHONE. नीचे. रखो!",
                "नालायक! पूरी team तुम्हारे भरोसे है! Laptop पे आओ, अभी!",
            ],
        },
        welcome_back=["ये हुई ना team! All is well! खेलते रहो!", "वापस crease पे! Good! खेलते रहो!", "ये हुई ना batting! रुकना नहीं!", "शाबाश! Run rate फिर से ऊपर!"],
        excuse_first=["अच्छा अच्छा… ठीक है, देखते हैं।", "अच्छा अच्छा… okay।"],
        excuse_repeat=["फिर वही बहाना? Third umpire भी नहीं मानेगा!", "बहाना नंबर दो! ये no ball है!"],
        followup=["{topic} अभी तक? या phone पे boundary लग रही है?", "{topic}? इतनी लंबी innings? सच बोलो!"],
        confess=["सच बोला! ये sportsman spirit है! अब काम!", "Honesty का full marks! चलो, practice शुरू!"],
        back_to_work=["That's my girl! Six लगाओ!", "ये हुई ना बात! Match हमारा है!"],
        unclear=["क्या? ज़ोर से बोलो, stadium में आवाज़ नहीं आई!", "फिर से बोलो! साफ़!"],
        caught=["Screen पे {site}? मुझे पता है! ये fielding है?", "पकड़ी गई! {site} चल रहा है, और match हाथ से जा रहा है!"],
        busted=["पढ़ाई? Screen पे {site} है! ये तो clear out है!", "झूठ! {site} खुला है! DRS भी तुम्हारे ख़िलाफ़ है!"],
        fake_comeback=["Mouse हिलाने से run नहीं बनते! {site} बंद करो!", "Shadow practice नहीं चलेगी! {site} अभी भी खुला है!"],
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
