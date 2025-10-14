import discord

from discord import app_commands
from discord.ext import commands
from discord.ui import Button, View

characters_dict = {
    "Wanderer": {
        "line": "USER, give me your hand. Heh, there's no need to be nervous. I'm just taking you to a vantage point.\nHow is it? The scenery here should be quite breathtaking. There's no need to thank me — I see little point in it.",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/f/f8/Wanderer_Icon.png",
        "birthday": "01-03",
    },
    "Lan Yan": {
        "line": "In my family, we always give silver accessories as birthday gifts. So, here, these two figures are for you. The one with the silver swallow on the head is me, and the one with the silver flower\u200d is you. Hehe, looks just like us, right? I infused the rattan strands with incense, so hanging them on your knapsack should repel insects. Oh, and I designed the silver accessories, too. The silversmith polished them once, and I made sure to smooth out the edges a second time, so you don't have to worry about cutting yourself. Well, happy birthday, USER! May luck always be on your side!",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/e/e6/Lan_Yan_Icon.png",
        "birthday": "01-06",
    },
    "Thoma": {
        "line": "Quick, USER, come with me! I remembered it's your birthday, obviously, so I thought I'd throw you a proper party. There's food, there's drinks, and I invited a whole bunch of your friends, too. Hey, this is your birthday we're talking about! I wasn't about to let you spend it all alone!",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/5/5b/Thoma_Icon.png",
        "birthday": "01-09",
    },
    "Chevreuse": {
        "line": "Happy Birthday, USER! Ahem... At attention! Chin up, shoulders back! Let's take your measurements... I want to commission a smaller, more portable musket and holster for you...\nOkay, at ease. While the musket is being commissioned, you need to log some hours at the shooting range first. No time like the present! Follow me!",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/8/8a/Chevreuse_Icon.png",
        "birthday": "01-10",
    },
    "Diona": {
        "line": "Here you go — fried fish with my special sauce! ... Relax, USER, I didn't add anything strange! My cooking is actually really good when I want it to be — stop talking and try it already! Hmph... that's better... Oh, and uh, happy birthday, USER.",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/4/40/Diona_Icon.png",
        "birthday": "01-18",
    },
    "Citlali": {
        "line": "Happy birthday, USER! Honestly, I don't know what to get you. There are no inauspicious stars in your path. Whether in regard to love, battle, or your future endeavors, your prospects seem great. A Mictlan-style blessing won't do much for you. I thought about getting you a copy of \"Flowers for Princess Fischl\" to get you hooked on light novels, but it seems like someone owns more books from Yae Publishing House than me... Ahh, what to do... what to do?",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/d/dd/Citlali_Icon.png",
        "birthday": "01-20",
    },
    "Kirara": {
        "line": "Happy birthday, USER! It doesn't matter if you're a human or a youkai, coming into this world is always worth celebrating! If you want, I can take you to the place I grew up in. It's not bustling with people, and it's not all that interesting, but it always makes me feel relaxed. Oh, and I'll let you sleep inside my favorite box, too! Having a nap inside it always feels great!",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/b/b6/Kirara_Icon.png",
        "birthday": "01-22",
    },
    "Rosaria": {
        "line": "Today's your birthday, USER, so if you have any dirty work that needs taking care of, I can give you a hand... Just don't tell anybody, got it?",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/3/35/Rosaria_Icon.png",
        "birthday": "01-24",
    },
    "Lynette": {
        "line": "Happy Birthday, USER! Let me give you this card... it's not a greeting card, so of course nothing's written on it. Write down what kind of present you want, place it in my hat, and no matter what it might be, you'll get it.",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/a/ad/Lynette_Icon.png",
        "birthday": "02-02",
    },
    "Lyney": {
        "line": "I have a feather here, just an ordinary feather... Go ahead, you can hold it and see for yourself. Ready? And... boom! It was a party popper all along. Happy Birthday, USER! See this? I caught one of the paper streamers floating down. Now, make a wish and picture a birthday gift in your mind's eye as I light it. Three... two... one... Great! Verrry good, I know exactly what you were thinking now. The last step, put your hand inside my hat... Well? Is it the gift you wanted?",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/b/b2/Lyney_Icon.png",
        "birthday": "02-02",
    },
    "Alhaitham": {
        "line": "Happy birthday, USER. I've always thought people are a little too enthusiastic about celebrating the day they were born. Wouldn't it be better to apply all that enthusiasm towards their daily lives and improve their standards of living? But you seem to have done well for yourself. I didn't know what kind of gift to get, so I'll just set up a special application channel, reserved for your submissions alone.",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/2/2c/Alhaitham_Icon.png",
        "birthday": "02-11",
    },
    "Beidou": {
        "line": "Come, board my ship. I've gathered the crew. The food and drink are all prepared. Today is your birthday, USER, so you are the captain. Haha, so: where should we set sail?",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/e/e1/Beidou_Icon.png",
        "birthday": "02-14",
    },
    "Kokomi": {
        "line": "Happy birthday, USER! So, what are your plans for the day? Oh, why don't we celebrate on Watatsumi Island? First, I'll take you out at daybreak to see the sunrise, then we can go diving during the heat of the day. In the evening, we can go for a stroll around Sangonomiya Shrine. If it rains, we'll find somewhere cozy to hide out with a few strategy books, and try to bake a cake together! In any case, no need to plan anything, the grand strategist has everything thought out for you!",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/f/ff/Sangonomiya_Kokomi_Icon.png",
    },
    "Bennett": {
        "line": "Happy birthday, USER! Best of luck in the year ahead. Don't worry, bad luck isn't contagious! As long as I'm around, it'll be drawn to me and not you, so you're safe.",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/7/79/Bennett_Icon.png",
        "birthday": "02-29",
    },
    "Qiqi": {
        "line": "Many happy returns, USER. Here is a bag of herbal medicine for you. You must be very surprised that I remembered? Let me explain. Last time you told me, I wrote your birthday down on a piece of paper. If I look at something once a day, it eventually goes into my long-term memory, and it will stay there forever.",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/b/b3/Qiqi_Icon.png",
        "birthday": "03-03",
    },
    "Yaoyao": {
        "line": "This is the day of your birth, USER! And as is tradition, this calls for a bowl of longevity noodles. I got Xiangling to teach me how to make it, and I managed to put all the noodles in the water without breaking a single one! I also put a big plump egg in there, hee-hee! Come on, USER, let's go, you've got to eat it before it goes cold. Wishing you a happy, healthy birthday and a long and prosperous life.",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/8/83/Yaoyao_Icon.png",
        "birthday": "03-06",
    },
    "Shenhe": {
        "line": "I've been told that birthdays are important occasions for most people. They give presents to celebrate the anniversary of the other person's birth. Material possessions aren't really my thing, but... The view of the starry night sky in the mountains is the most beautiful thing I've ever seen in my life. I've frozen this lake and turned it into a mirror, so you can appreciate the reflection of the fleeting clouds and distant stars right up close. This is my way of celebrating your birthday, USER... Hope you like it.",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/a/af/Shenhe_Icon.png",
        "birthday": "03-10",
    },
    "Xilonen": {
        "line": "Happy Birthday, USER. Here, this universal multi-tool set is yours to keep. It has a variety of drills and hammers, as well as three hand saws and five special-shaped prybars, which should come in handy for you in the wild. Oh, and there is also a set of ropes made from woven leather and metal wire. They should be strong enough to lift even a fully-grown Tepetlisaur. Do you know how to tie knots? If not, I can teach now. Here, watch... First, hold the rope like this, then loop it around...",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/a/ab/Xilonen_Icon.png",
        "birthday": "03-13",
    },
    "Jean": {
        "line": "Today is a day worth celebrating. If you must ask why, well, let me remind you that today is when you, the one who is blessed by the wind, came into the world. Since this is your birthday, I'll allow you to take it easy.\nAhem... ♪ Happy birthday to you, USER... ♪\nUh... Please forgive my presumptuousness. I hope this gift is to your liking.",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/6/64/Jean_Icon.png",
        "birthday": "03-14",
    },
    "Mizuki": {
        "line": "Today is a very special day for the both of us. Meeting you has given me the chance to witness a wondrous world of endless dreams... So, why don't we celebrate this occasion with a dreamscape for just the two of us? Of course, we'll need to build it from the ground up. So, tell me what you'd like to see, USER...",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/f/f6/Yumemizuki_Mizuki_Icon.png",
    },
    "Noelle": {
        "line": "Since you're always so busy adventuring, there must be so many little things you never get round to, surely? Well, you need not worry about them adding up, because today, I am all yours — your exclusive maid for the entire day! Just leave it all to me, USER! ...Also, I'd like to take this opportunity to wish you a very happy birthday!",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/8/8e/Noelle_Icon.png",
        "birthday": "03-21",
    },
    "Ifa": {
        "line": "Happy birthday, USER! Wishing you good health and eternal youth. Sure, you can't stop the relentless march of time, but you can always stay young at heart — and besides, dude, a bad mood doesn't do your health any good. So come on, just for today, cast your worries aside and let's have some fun!\n\nOh yeah, also, what kind of music are you into? I'll play a song.",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/5/5f/Ifa_Icon.png",
        "birthday": "03-23",
    },
    "Ayato": {
        "line": "Happy Birthday, USER! Now, how would you like to be Yashiro Commissioner for a day, hmm? All the work has been handled already, so you can focus on simply enjoying the feeling of having an enormous amount of executive power at your fingertips. Don't worry, the retainers won't dare question it, I'll be with you the entire time, hehe.",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/2/27/Kamisato_Ayato_Icon.png",
    },
    "Sigewinne": {
        "line": "Happy Birthday, USER! From what I've observed, you're always going from one place to the next. So, I made a special skincare set just for you that's portable and practical. Come on, lay down and close your eyes, I'll show you how to use it. First, I'm gonna apply a wet compress to your face — but you can just splash some water on there if you're ever in a hurry... Next, we squeeze out a small amount of foam cleanser, gently massaging it in with a circular motion, following the muscle, before rinsing and drying... And lastly, we apply some moisturizer with Tidalga extract... And, we're done! You look radiant, and now it's time for lovely little you to go and enjoy your special day to the fullest!",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/3/37/Sigewinne_Icon.png",
        "birthday": "03-30",
    },
    "Aloy": {
        "line": "Never put much stock in birthdays. Where I come from, it's a time to celebrate your mother, not yourself. Even so, I wish you a, uh... happy day, USER.",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/e/e5/Aloy_Icon.png",
        "birthday": "04-04",
    },
    "Dehya": {
        "line": "Happy Birthday, USER! Reach into your pocket, your present's already in there. How'd I do it? Hehe, just a little trick of the trade. Anyway, more importantly, I've booked us a real feast at Lambad's Tavern, so let's get ourselves over there! ...Huh? Oh, don't worry, I didn't invite any of the other mercs. Nah, that rowdy bunch is always getting into arguments — not the kind of people you'd want at a birthday celebration. It'll just be me and you, like it should be... Ahem, c'mon, c'mon, let's go.",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/3/3f/Dehya_Icon.png",
        "birthday": "04-07",
    },
    "Charlotte": {
        "line": "Happy Birthday, USER! Did you read today's Steambird yet? I put a birthday greeting in there for you, hehe... Wait, you still haven't bought a copy? No problem, I picked one up before leaving the office. Look — here it is! I fought pretty hard to get it on this page.",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/d/d2/Charlotte_Icon.png",
        "birthday": "04-10",
    },
    "Xianyun": {
        "line": "Here, USER, open this wooden box. It's a miniature mechanical person for your recreational enjoyment. Try playing with it. Observe — if you clap the hands like this, the lotus petals open, the colored lights turn on one set at a time, and then a melody plays. It is that birthday tune that the young and hip of this generation enjoy so much. Certain to add a touch of merriment and levity to your birthday feast... Have a wonderful day.",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/d/d3/Xianyun_Icon.png",
        "birthday": "04-11",
    },
    "Xiao": {
        "line": "This mortal concept of commemorating the day of your birth really is redundant. Wait, USER. Have this. It's a butterfly I made from leaves.\nOkay. Take it, USER. It's an adepti amulet — it staves off evil.",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/f/fd/Xiao_Icon.png",
        "birthday": "04-17",
    },
    "Yelan": {
        "line": "If I was to tell you that maybe you shouldn't celebrate too hard today, because you'll let your guard down, and someone out there might just be waiting for that moment to make their move on you... it probably wouldn't go down very well. So USER, relax and take it easy today. Oh, and you should stop by the Yanshang Teahouse — I whipped up some treats especially for you. Not sweet ones, of course. Just the tiniest little hint of chili.",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/d/d3/Yelan_Icon.png",
        "birthday": "04-20",
    },
    "Kachina": {
        "line": "Happy birthday, USER! This is for you. It's a pika carved from Iridescent Opal. Iridescent Opal's quite warm to the touch, but it doesn't really stand out, so it's easy to miss it underground. The more you carry it with you, though, the shinier it gets! It's one of my favorite gems, so I hope you'll like it too.",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/1/1a/Kachina_Icon.png",
        "birthday": "04-22",
    },
    "Baizhu": {
        "line": "I hope that this day will be one filled with joy every year, and that you would always keep these times near. Happy Birthday, Traveler USER!",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/c/cb/Baizhu_Icon.png",
        "birthday": "04-25",
    },
    "Diluc": {
        "line": "Happy birthday, USER. This is an important day for you. So tell me, what is it you wish for? If it is within my power to bestow it upon you, I will give it my consideration.",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/3/3d/Diluc_Icon.png",
        "birthday": "04-30",
    },
    "Candace": {
        "line": "Happy birthday, USER! It's amazing to think that you were born on this day, years ago in the past. Do you have a birthday wish? If it involves going somewhere dangerous, let me join you — I'll be your guard. Or if you're looking to rest and revitalize, come to Aaru Village, and I'll serve you the finest meats and drinks we have.",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/d/dd/Candace_Icon.png",
        "birthday": "05-03",
    },
    "Collei": {
        "line": "Uh, H—Happy Birthday, USER! Here's the cake I made for you, and here are the candles, so yeah... Amber said in her letter that this would do the job... Oh! And, and here's the gift I got for you!\n...I'm sorry, I don't have much experience arranging birthday parties. I have no idea if you'll like it... Aah, I'm getting all flustered now. If anything's not how you like it, please say, and I'll make absolutely sure to plan a nicer birthday celebration for you next year!",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/a/a2/Collei_Icon.png",
        "birthday": "05-08",
    },
    "Gorou": {
        "line": "Today's a momentous occasion, your birthday, USER! Allow me to arrange all the celebrations for you! We can make a bonfire on the beach and catch some fresh fish and crabs. I'll personally prepare a morale-boosting meal that would make even the highest-ranking generals jealous.",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/f/fe/Gorou_Icon.png",
        "birthday": "05-18",
    },
    "Yun Jin": {
        "line": "Oh, USER, so today's your birthday? Well, I wouldn't know how to throw you a feast if I tried... so how about I sing you a song? For you alone, an audience of one. So... what song would you like to hear me sing? The choice is yours.",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/9/9c/Yun_Jin_Icon.png",
        "birthday": "05-21",
    },
    "Fischl": {
        "line": "Well! If today is truly the anniversary of your birth, it shan't do for me not to mark the occasion. USER, you have my full attention. Speak! Speak to me of your wishes, that which you most desire to fulfill during your fleeting and harsh existence in this wretched world. Whatever that wish may be.",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/9/9a/Fischl_Icon.png",
        "birthday": "05-27",
    },
    "Sethos": {
        "line": "You know, USER, your hair would look amazing if it was done up in a desert-dweller style... How about kicking off the next year of your life with a new hairdo, huh? If you're up for it, just leave it to me. You'll look glamorous, I promise you.",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/9/90/Sethos_Icon.png",
        "birthday": "05-31",
    },
    "Itto": {
        "line": "Today's an important day. I had to send the gang away, otherwise they'd be accusing me of favoritism. Here, take a look at this. I got you the greatest birthday gift combo ever! One top-grade Onikabuto — I'll have you know it took me three whole days and nights to catch this bad boy — one out-of-print collectible trading card that took me 300 rounds to get my hands on, and finally, a birthday song performance performed personally by yours truly! Happy Birthday to you, Happy Birthday to you, Happy Biiiirthday dear USER, Happy Birthday to youuuu!",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/7/7b/Arataki_Itto_Icon.png",
    },
    "Escoffier": {
        "line": "Esteemed Traveler, USER, you are the \"ultimate variable\" of Teyvat, the one who brought a unique flavor to this world. A birthday celebration in your honor calls for a feast with eighty dishes at least — four meat, four wild game, four pastry, and two soup dishes, just to start... Still, gorging on food is no way to dine — it's a disservice to your health and to the dishes themselves... Thus, we shall just have to celebrate your birthday over the entire week! Ten dishes a day should do it. I want you to appreciate each one to the fullest. A culinary symphony awaits!",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/2/2a/Escoffier_Icon.png",
        "birthday": "06-08",
    },
    "Lisa": {
        "line": "Here, take this amulet, it will bring you good luck. It's my birthday gift to you, USER. I spent a long time making it, so don't lose it now!",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/6/65/Lisa_Icon.png",
        "birthday": "06-09",
    },
    "Venti": {
        "line": "Someone once told me you're supposed to eat a cake on your birthday... Tada! Here's your birthday cake, USER — it's apple flavored! And here's a spoon. The cake didn't rise properly in the oven, that's why it looks more akin to an apple pie... Ugh, baking is really quite complicated!",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/f/f1/Venti_Icon.png",
        "birthday": "06-16",
    },
    "Yoimiya": {
        "line": "Birthdays are never occasions for yourself alone, USER. Those who send you cakes, light candles, applaud, and cheer... They are all truly thankful that you were born into this world. That's why it must be a lively occasion, so that everyone can get their chance to thank you! Well then — happy birthday! Are you ready? I'm about to ignite the fireworks!",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/8/88/Yoimiya_Icon.png",
        "birthday": "06-21",
    },
    "Cyno": {
        "line": "Ahem... I'd like to wish you a happy birthday, USER. Though I don't have much experience with celebrations, once I realized your birthday was coming, I decided to make some preparations. First, I have this deck for you that I worked on for a few days, I think it'll really suit your style. Also, I adjusted my schedule to open up some time, so is there anywhere you'd like to go? I'd be happy to accompany you. A birthday only lasts a day, but you should take the chance to really enjoy it. Just make sure we can be back within three days.",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/3/31/Cyno_Icon.png",
        "birthday": "06-23",
    },
    "Raiden Shogun": {
        "line": "Happy birthday, USER! Let's celebrate together and make it a moment to remember for the whole year until your next birthday celebration, and so on and so forth. Then, you shall have an eternity of happiness.",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/2/24/Raiden_Shogun_Icon.png",
        "birthday": "06-26",
    },
    "Yae Miko": {
        "line": 'Ah, so today is your birthday, USER... "On your ceremonious reckoning of years, I task my kin with seeing to it that that which you seek, you shall surely find, and that that for which your heart longs, you shall surely receive. Remain pure of heart and true of spirit, and their protection shall be bestowed on you." There you go. May all go well in your year ahead, and may all your wishes be fulfilled. Are we done?',
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/b/ba/Yae_Miko_Icon.png",
        "birthday": "06-27",
    },
    "Barbara": {
        "line": "Here you go! This is the gift I got for your birthday, USER, along with my exclusive autograph! Hehe, when my next song comes out, I'll make sure you're the first one to hear it! Happy birthday, USER!",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/6/6a/Barbara_Icon.png",
        "birthday": "07-05",
    },
    "Kaveh": {
        "line": "Is it your birthday today, USER? Well, congratulations! Birthdays are important days, and it's also one of those days in the year that gets you thinking about your family. However you spend today, I hope it makes you happy.",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/1/1f/Kaveh_Icon.png",
        "birthday": "07-09",
    },
    "Sara": {
        "line": "Excellent timing, USER. I will dispense with the formalities and get straight to the point — do you have a birthday wish? Providing that it does not conflict with the Almighty Shogun's grand cause, I will make every effort to see it come to fruition. To show that I am being completely serious, I will allow you to make not one, but five birthday wishes.",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/d/df/Kujou_Sara_Icon.png",
    },
    "Hu Tao": {
        "line": "Tonight the stars are dazzling and the moon majestic, it must be a special day... But just what day could it be... Haha, I know, I know! It's your birthday, USER! It really is a great day.",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/e/e9/Hu_Tao_Icon.png",
        "birthday": "07-15",
    },
    "Tartaglia": {
        "line": "Happy birthday, comrade USER! Anyone you need knocked off their perch today? Let me know. I'll happily oblige...",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/8/85/Tartaglia_Icon.png",
        "birthday": "07-20",
    },
    "Heizou": {
        "line": "USER, after I learned that today was your birthday, there was a brief moment when I really wanted to take you to a locked room chock-full of mechanisms and gifts, where you could only get out by solving all the puzzles... Hehe, it's actually really fun! You know, of course I wouldn't do anything like that unless I was sure you'd actually enjoy it. Here, come with me. There's this beautiful scenic spot I've gotta show you before the sun goes down.",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/2/20/Shikanoin_Heizou_Icon.png",
    },
    "Klee": {
        "line": "♪ Happy birthday to you, happy birthday to you, happy birthday dear traveler, happy birthday to you, USER! ♪ You're older than me right? That means you've had way more birthdays than me... I'm sooo jealous!",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/9/9c/Klee_Icon.png",
        "birthday": "07-27",
    },
    "Shinobu": {
        "line": "Happy birthday, USER! Here, take this special dart made from Naku Weed. Be careful, yep, that's the way to hold it... Make sure you predict the trajectory before you throw it... Hehe, I'm happy that you like it. Oh, don't treat it like a toy, it's still quite dangerous. If you want to practice a little more, I can teach you.",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/b/b3/Kuki_Shinobu_Icon.png",
    },
    "Yanfei": {
        "line": "Happy birthday, USER! Here, this is for you. I've collated legislation from all the nations — you're planning to go traveling, right? It will serve you well to familiarize yourself with the law of the different lands.\nDon't study too hard mind you, or else... I won't be of any use to you.",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/5/54/Yanfei_Icon.png",
        "birthday": "07-28",
    },
    "Mualani": {
        "line": "Happy birthday! Don't open your gifts just yet. I picked this restaurant just for you, it's the most popular one around... I bet you've already gotten loads of well-wishes from your friends, but what if I told you even more people from your journey wanted to help you celebrate? What do you think?\n\nHehe! C'mon, have a seat and let's bring on the birthday wishes! Ahem... Excuse me, @everyone! Your attention, please! Today is my friend's birthday! A noble and formidable hero who's defeated ferocious beasts and healed countless souls! C'mon, let's give them our warmest birthday wishes! Alright, you guys over there, say it with me, \"Here's to good fortune on your adventures!\" Great! And you guys over there... \"Here's to success in battle!\" Perfect! Finally, all together, now... Happy birthday, USER! Here's to good luck, good health, and much happiness!",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/0/0b/Mualani_Icon.png",
        "birthday": "08-03",
    },
    "Iansan": {
        "line": "Happy birthday, USER! Would you like to try my custom-made fitness cake? There's no cream or sugar, so it's low-calorie, and I added in some veggies and grains to balance out the nutritional profile. Most birthday cakes out there are dangerous things to have around. All they do is make sure your body fat percentage goes up every year along with your age...",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/3/38/Iansan_Icon.png",
        "birthday": "08-08",
    },
    "Amber": {
        "line": "Hey, happy birthday, USER! Here, I have a gift for you: an exclusive, custom-made version of Baron Bunny that I sewed for you myself. Uh... don't worry, \"custom-made\" means that it won't explode!",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/7/75/Amber_Icon.png",
        "birthday": "08-10",
    },
    "Mika": {
        "line": "Oh, what should we do for an occasion like this? Hmm... Today is your most special day, USER, so we should really live it up! I've prepared \"A Tour of Mondstadt's Most Stunning Spots.\" It contains information on lots of beautiful locations that are hardly known to anyone else. I wish you happiness every day until this day arrives again next year.",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/d/dd/Mika_Icon.png",
        "birthday": "08-11",
    },
    "Navia": {
        "line": "Do you believe that wishes can come true? You know, like when you toss a coin into a fountain for good luck? As long as you throw enough coins in, one of your wishes is sure to come true, right?\nWell anyway, today's your birthday, USER, so I'm not leaving anything to chance — I've got a whole bag of Mora here dedicated to making your birthday wish come true. Whatever you want, I'll do everything in my power to make it happen!",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/c/c0/Navia_Icon.png",
        "birthday": "08-16",
    },
    "Chiori": {
        "line": "Yeah, yeah... Happy birthday, or whatever, USER. Just tell me if there's a gift you like — I can't be bothered to try and guess what you want. Hm? Too direct? Alright then, why don't you grab Navia, Kirara, and the others, and maybe a few of your friends as well. We can have a party tonight at my place. I'll take some notes on the gifts that the others have prepared for you, and make you an accessory right then and there. Ten thousand mora that you'd like it. Haha, call it the confidence of the owner of Chioriya Boutique.",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/8/88/Chiori_Icon.png",
        "birthday": "08-17",
    },
    "Faruzan": {
        "line": "Happy birthday, USER! Here's a small toy for you. It's an assembly of a number of miniature puzzle mechanisms — you can find a button and lever here, as well as a roller to the side. Just play with it however you want, and I'll take care of it if it breaks. Hmph, and don't think I'm treating you like a child. Everyone, regardless of age, could use a moment of happiness and relaxation.",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/b/b2/Faruzan_Icon.png",
        "birthday": "08-20",
    },
    "Arlecchino": {
        "line": "This memo states that today is your birthday. Is that true? Birthdays should be lively occasions. It's always nice to have an excuse to set formal matters aside every now and then, whether it's for the purpose of celebrating yourself or others. Come, USER. I've prepared a feast for you at the House of the Hearth. Let's not keep the children waiting.",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/9/9a/Arlecchino_Icon.png",
        "birthday": "08-22",
    },
    "Ningguang": {
        "line": "These are some of Liyue's finest brocades, woven from silk flowers. This one is for you, USER, and I hope that you'll like it. I wish you a happy birthday.",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/e/e0/Ningguang_Icon.png",
        "birthday": "08-26",
    },
    "Mavuika": {
        "line": "Starting from today, you should write down all your accomplishments on a piece of paper. Then, when you take it out on your next birthday, you'll have a gift from yourself! That way, you'll never forget how amazing you are. Happy Birthday, USER.",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/d/da/Mavuika_Icon.png",
        "birthday": "08-28",
    },
    "Mona": {
        "line": "Happy Birthday, USER. Here's my gift to you — it's a bag containing some words of advice that may help you through tough patches.\n...No, don't open it yet. During the year ahead, this bag will open itself when the right time comes.",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/4/41/Mona_Icon.png",
        "birthday": "08-31",
    },
    "Chongyun": {
        "line": "On the anniversary of your birth, please accept this gift of a flower, made of ice crystals. I carved it myself. If you ever encounter an evil spirit, cast this toward it — the spell I have cast upon it will immediately come into effect and hopefully get you out alive. Also... Happy birthday, USER.",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/3/35/Chongyun_Icon.png",
        "birthday": "09-07",
    },
    "Razor": {
        "line": "Today is your day, USER. You were born on this day, many moons ago. I want to make you happy today. Can we eat meat together?",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/b/b8/Razor_Icon.png",
        "birthday": "09-09",
    },
    "Albedo": {
        "line": "Happy birthday, USER. You look especially happy, would you mind if I sketched you? The capacity of our brains is limited, so we are bound to forget things. But when an image is transferred onto paper or canvas, the sketch becomes an extension of our memory. We can remember that past feeling when we later look at the sketch.",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/3/30/Albedo_Icon.png",
        "birthday": "09-13",
    },
    "Clorinde": {
        "line": "Happy Birthday, USER. I have a gift for you — it's a short-sword necklace that I made myself. In the Marechaussee Hunters' tradition, on a new member's first birthday as a hunter, (\u200dhis/her\u200d) mentor will make (\u200dhim/her\u200d) a short-sword necklace with (\u200dhis/her\u200d) name engraved, to be worn with the sword hanging over the chest. This is to symbolize interrogating (\u200dhis/her\u200d) own heart at swordpoint: Will I tread the path of treachery, is there doubt in my heart, or am I resolved to eradicate all evil? Though you're not a Marechaussee Hunter, I believe that you're committed, like I am, to fighting the good fight. Why a sword, and not a musket? Because guns can misfire. Also, there's something a little inelegant about interrogating your heart at gunpoint.",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/5/5b/Clorinde_Icon.png",
        "birthday": "09-20",
    },
    "Emilie": {
        "line": "Happy birthday, USER! I know perfume preferences are extremely personal, but I took the liberty of choosing one I think you'll like. It's one of my own creations, actually, but it's not available to purchase yet. I tried to combine the floral and fruity notes found in nature around this time of year. I was going for more of a subtle scent. Anyway, I hope it brings you a little peace and comfort whenever you wear it.",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/a/aa/Emilie_Icon.png",
        "birthday": "09-22",
    },
    "Freminet": {
        "line": "Would you be willing to come with me somewhere, USER? There's this place I know where the scenery is spectacular. I think it's even more magical than a fantasy novel. I have a secret hideout there, and I keep some glowing sea creatures as pets... I just want to give you a birthday experience like you've never had before, and then give you my birthday wishes... Will you give me the chance to do that, USER?",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/e/ee/Freminet_Icon.png",
        "birthday": "09-24",
    },
    "Ayaka": {
        "line": "Come with me! We're not going far away — I promise it won't delay you too much.\nI managed to find out when your birthday was well in advance, USER, so I could prepare in good time. Hopefully this wasn't assuming too much, but I guessed you might prefer this to an expensive gift.\nIn honor of your birthday, please allow me to perform a fan dance for you.",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/5/51/Kamisato_Ayaka_Icon.png",
    },
    "Xingqiu": {
        "line": "May this day of your birth be filled with much mirth, USER!\nAccording to historical records, Tiancheng's stone bridge was formed by a fallen rock spear thrown by the Geo Archon Morax in battle. If you walk along the bridge on your birthday and throw some Mora into the sea from both sides, you will be blessed in the coming year... \nUSER, your birthday only comes once a year, so be quick about it if you wanna go... I'm not kidding, it's true! Go try it and you'll see!",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/d/d4/Xingqiu_Icon.png",
        "birthday": "10-09",
    },
    "Furina": {
        "line": "Happy Birthday, USER! Here, please take this ticket as your gift. It's a VIP seat to see Happy Day, just don't forget to show up to the performance! Hmm? What's \"Happy Day\"? *sigh* Well, I wanted to keep it a surprise... But it's an opera that I've rehearsed personally. It's about a big group of people that gather together to celebrate a certain very important person. You understand now, right? Just don't forget to come!",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/e/e6/Furina_Icon.png",
        "birthday": "10-13",
    },
    "Ororon": {
        "line": "In Natlan, we believe a person's birthday decides their fate. Sharing a birthday with a great hero means being blessed with their protection and inheriting their character. \nI'm not sure the people out there who share your birthday know how lucky they are... Happy Birthday, USER.",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/5/5e/Ororon_Icon.png",
        "birthday": "10-14",
    },
    "Xinyan": {
        "line": "Happy birthday, USER! I made some embroidery especially for you. Check it out — I sewed both our images on in the style of Fontaine's dolls. Pretty cute, eh? ...Why are you looking at me like that? Wh—What, it's not that weird that I can do embroidery!",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/2/24/Xinyan_Icon.png",
        "birthday": "10-16",
    },
    "Sayu": {
        "line": "Wanna learn some ninja skills, USER? I can teach you! Well, only the skills I know, of course. Hmm? Why aren't I asleep? ...Uhh, because I'm not sleepy... and also because today is a special day! I had to stay awake today so I'd have the chance to say it to you in person: Happy Birthday, USER.",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/2/22/Sayu_Icon.png",
        "birthday": "10-19",
    },
    "Eula": {
        "line": "Today is a day worth observing, though you shouldn't mark your development in age alone, USER. Accept my gift of a bone whistle, and allow me to teach you its secrets. When your day of reckoning comes, see how long you can fend me off with it... It'll make the whole thing much more exciting.",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/a/af/Eula_Icon.png",
        "birthday": "10-25",
    },
    "Nahida": {
        "line": "I was thinking, USER, that your birthday celebration needs to be at least as grand as the Sabzeruz Festival, so... Hmm? Too much? But everyone's already done preparing for it. C'mon, c'mon, USER, let's go! Just this once — I'll make sure you love it!",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/f/f9/Nahida_Icon.png",
        "birthday": "10-27",
    },
    "Kazuha": {
        "line": "I heard it was your birthday, USER, so I wrote a haiku for you. Unfortunately, I'm not the most talented in this area, and after trying for several evenings, I was still only able to come up with the first two lines... I guess I'll just share what I've got so far, then. \"Sun and moon rejoice / Birds of dawn sing songs anew\"... Wait, don't say a word, I think the final line is coming to me... Yes, how about.... \"Far from home, with you.\" Anyway, Happy Birthday. Let's go and get you some cake, shall we?",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/e/e3/Kaedehara_Kazuha_Icon.png",
    },
    "Xiangling": {
        "line": "Ah, USER, there you are! Come with me, I've prepared a birthday feast all for you! ... No really, USER, I insist! Which dish is your favorite? It's okay, take your time, try them all first, then let me know!",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/3/39/Xiangling_Icon.png",
        "birthday": "11-02",
    },
    "Kinich": {
        "line": "Just follow me. Don't worry, it's just a gentle cruise through the forest. I planned out a route in advance and I promise it's safe. Alright, now hop on... Happy birthday USER.",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/9/9a/Kinich_Icon.png",
        "birthday": "11-11",
    },
    "Varesa": {
        "line": "Heehee... Today's your birthday, USER. I'm so excited! The tradition in our tribe is to get all your friends together and host a bonfire feast in your honor. The birthday person gets to cheers everyone and drink as much as they want! Although... with you being so famous, I guess you'd end up having to down at least a thousand drinks... Which would be great fun, I'm sure, but probably not the best thing for your liver. And it could get exhausting, too... Hmm, how about something more low-key instead? Like... a private party at my secret campsite?",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/d/dd/Varesa_Icon.png",
        "birthday": "11-15",
    },
    "Keqing": {
        "line": "Happy birthday, USER! I've got a very special gift for you. It might look like an ordinary old lantern, but this one runs on Electro energy and stays alight for a really long time. For those times when you need a little extra light in your life.",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/5/52/Keqing_Icon.png",
        "birthday": "11-20",
    },
    "Wriothesley": {
        "line": "Our tradition says that all children of Fontaine are born amid their parents' wishes and blessings, but I'd like to think that all children are born from such wonderful feelings. Anything that I can say to celebrate your birth would feel a little trivial next to that, right, USER?\nUnfortunately, I won't be able to reduce your prison sentence if you were to commit a crime — the only thing I would be able to pull off would be a special Welfare Meal for your birthday dinner. With all that in mind, why don't you try to respect the law a bit more around your birthday, so we'll be able to celebrate somewhere nice on the surface?",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/b/bb/Wriothesley_Icon.png",
        "birthday": "11-23",
    },
    "Sucrose": {
        "line": "Happy birthday, USER! I've been running experiments for months, and finally I can give you this potion. It will allow you to relive your most beautiful memories of the past year. I call it \"Bio-Potion No. 3916.\" Huh? No, no, not 3196, it's 3916!",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/0/0e/Sucrose_Icon.png",
        "birthday": "11-26",
    },
    "Kaeya": {
        "line": "Today is a day worth celebrating, I hope this day can bring you true happiness, USER.",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/b/b6/Kaeya_Icon.png",
        "birthday": "11-30",
    },
    "Ganyu": {
        "line": "Many happy returns, USER! After all the times you've looked out for me, I didn't even remember to get you a gift — whoops! Silly me, I... What's that behind my back? Ah. You saw it then. It's a failed attempt at making a Qingxin Flower cake... I wanted it to be perfect, but... Oh, you think it tastes good? Do you really?",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/7/79/Ganyu_Icon.png",
        "birthday": "12-02",
    },
    "Nilou": {
        "line": "Umm... Happy birthday, USER! I learned a new dance, and I want to show it to you. Uh, am I nervous? *sigh* You saw right through me. It's because... I wanted to incorporate my feelings into the moves, but then the choreography just got more and more difficult... Anyway, I just wish that your life will always be full of wonder and happiness.",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/5/58/Nilou_Icon.png",
        "birthday": "12-03",
    },
    "Chasca": {
        "line": "Ooh, you got the special round on the first try, huh? Luck's on your side today, USER... That was a whistling birthday firework. I made it myself! Hmm? ...What are the other five rounds? More fireworks, of course! But they're the trial runs that I made before the one you just fired off. The color's different, and they're not perfect. Next year, I'll do my best to make a full six top-quality rounds for you.",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/0/03/Chasca_Icon.png",
        "birthday": "12-10",
    },
    "Neuvillette": {
        "line": "Ah, so it's your birthday. Happy birthday, USER. I do not know if rain is in the forecast today, but let me see what I can do.",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/2/21/Neuvillette_Icon.png",
        "birthday": "12-18",
    },
    "Layla": {
        "line": "Happy birthday, USER. I got you this pocket astrolabe... The same stars witness the fate of the human race today as did yesterday, and as will forever. May they cast their gaze upon you, and may they stay with you always, through the desert and across the ocean, until you reach your destination.",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/1/1a/Layla_Icon.png",
        "birthday": "12-19",
    },
    "Dori": {
        "line": "Today I can grant you one wish, USER! After all, I am the great and almighty Dori! Go on, tell me, what do you wish for? But lemme just tell you now that a lifetime supply of Mora is off the table.",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/5/54/Dori_Icon.png",
        "birthday": "12-21",
    },
    "Gaming": {
        "line": "So a little birdie told me that it's your birthday today, USER... When were you planning on telling me? Tsk... Anyway, I went ahead and made a reservation at Xinyue Kiosk. Eight dishes, a soup, and as much rice as you can eat, with Longevity Buns and Tong Sui for dessert. Plus I invited all your friends along. Uh, and I also put together a little birthday wushou dance for you — nothing extravagant, just a bit of fun really — but yeah, I hope you like it!",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/7/77/Gaming_Icon.png",
        "birthday": "12-22",
    },
    "Tighnari": {
        "line": "Happy birthday, USER! I picked out a potted plant in full bloom for you, along with a gardening guide. If anything happens to it, don't hesitate to find me at any time. This plant comes with a Forest Watcher lifetime guarantee.\nI'll have you know a lot of flowers are in season on your birthday. It took me forever to choose one. I'll get you a different species next year!",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/8/87/Tighnari_Icon.png",
        "birthday": "12-29",
    },
    "Zhongli": {
        "line": "Happy birthday, USER. This is a dried Glaze Lily that came into bloom on the day of your birth. Long ago, the people of Liyue would say that this flower blooms bearing the weight of the beautiful memories and prayers of the land. I believe this to have been applied on the day you were born as well.",
        "icon": "https://static.wikia.nocookie.net/gensin-impact/images/a/a6/Zhongli_Icon.png",
        "birthday": "12-31",
    },
}

characters = list(characters_dict.keys())

timezones = ['America/Araguaina', 'America/Argentina/Buenos_Aires', 'America/Argentina/Catamarca', 'America/Argentina/Cordoba', 'America/Argentina/Jujuy', 'America/Argentina/La_Rioja', 'America/Argentina/Mendoza', 'America/Argentina/Rio_Gallegos', 'America/Argentina/Salta', 'America/Argentina/San_Juan', 'America/Argentina/San_Luis', 'America/Argentina/Tucuman', 'America/Argentina/Ushuaia', 'America/Asuncion', 'America/Bahia', 'America/Belem', 'America/Boa_Vista', 'America/Bogota', 'America/Campo_Grande', 'America/Caracas', 'America/Cayenne', 'America/Cuiaba', 'America/Eirunepe', 'America/Fortaleza', 'America/Guayaquil', 'America/Guyana', 'America/La_Paz', 'America/Lima', 'America/Maceio', 'America/Manaus', 'America/Montevideo', 'America/Noronha', 'America/Paramaribo', 'America/Porto_Velho', 'America/Punta_Arenas', 'America/Recife', 'America/Rio_Branco', 'America/Santarem', 'America/Santiago', 'America/Sao_Paulo', 'Antarctica/Palmer', 'Atlantic/South_Georgia', 'Atlantic/Stanley', 'Pacific/Easter', 'Pacific/Galapagos', 'America/Adak', 'America/Anchorage', 'America/Bahia_Banderas', 'America/Barbados', 'America/Belize', 'America/Boise', 'America/Cambridge_Bay', 'America/Cancun', 'America/Chicago', 'America/Chihuahua', 'America/Ciudad_Juarez', 'America/Costa_Rica', 'America/Dawson', 'America/Dawson_Creek', 'America/Denver', 'America/Detroit', 'America/Edmonton', 'America/El_Salvador', 'America/Fort_Nelson', 'America/Glace_Bay', 'America/Goose_Bay', 'America/Grand_Turk', 'America/Guatemala', 'America/Halifax', 'America/Havana', 'America/Hermosillo', 'America/Indiana/Indianapolis', 'America/Indiana/Knox', 'America/Indiana/Marengo', 'America/Indiana/Petersburg', 'America/Indiana/Tell_City', 'America/Indiana/Vevay', 'America/Indiana/Vincennes', 'America/Indiana/Winamac', 'America/Inuvik', 'America/Iqaluit', 'America/Jamaica', 'America/Juneau', 'America/Kentucky/Louisville', 'America/Kentucky/Monticello', 'America/Los_Angeles', 'America/Managua', 'America/Martinique', 'America/Matamoros', 'America/Mazatlan', 'America/Menominee', 'America/Merida', 'America/Metlakatla', 'America/Mexico_City', 'America/Miquelon', 'America/Moncton', 'America/Monterrey', 'America/New_York', 'America/Nome', 'America/North_Dakota/Beulah', 'America/North_Dakota/Center', 'America/North_Dakota/New_Salem', 'America/Ojinaga', 'America/Panama', 'America/Phoenix', 'America/Port-au-Prince', 'America/Puerto_Rico', 'America/Rankin_Inlet', 'America/Regina', 'America/Resolute', 'America/Santo_Domingo', 'America/Sitka', 'America/St_Johns', 'America/Swift_Current', 'America/Tegucigalpa', 'America/Tijuana', 'America/Toronto', 'America/Vancouver', 'America/Whitehorse', 'America/Winnipeg', 'America/Yakutat', 'Atlantic/Bermuda', 'Pacific/Honolulu', 'Africa/Ceuta', 'America/Danmarkshavn', 'America/Nuuk', 'America/Scoresbysund', 'Scoresbysund/Ittoqqortoormiit', 'America/Thule', 'Thule/Pituffik', 'Asia/Anadyr', 'Asia/Barnaul', 'Asia/Chita', 'Asia/Irkutsk', 'Asia/Kamchatka', 'Asia/Khandyga', 'Asia/Krasnoyarsk', 'Asia/Magadan', 'Asia/Novokuznetsk', 'Asia/Novosibirsk', 'Asia/Omsk', 'Asia/Sakhalin', 'Asia/Srednekolymsk', 'Asia/Tomsk', 'Asia/Ust-Nera', 'Asia/Vladivostok', 'Asia/Yakutsk', 'Asia/Yekaterinburg', 'Atlantic/Azores', 'Atlantic/Canary', 'Atlantic/Faroe', 'Atlantic/Madeira', 'Europe/Andorra', 'Europe/Astrakhan', 'Europe/Athens', 'Europe/Belgrade', 'Europe/Berlin', 'Europe/Brussels', 'Europe/Bucharest', 'Europe/Budapest', 'Europe/Chisinau', 'Europe/Dublin', 'Europe/Gibraltar', 'Europe/Helsinki', 'Europe/Istanbul', 'Europe/Kaliningrad', 'Europe/Kirov', 'Europe/Kyiv', 'Europe/Lisbon', 'Europe/London', 'Europe/Madrid', 'Europe/Malta', 'Europe/Minsk', 'Europe/Moscow', 'Europe/Paris', 'Europe/Prague', 'Europe/Riga', 'Europe/Rome', 'Europe/Samara', 'Europe/Saratov', 'Europe/Simferopol', 'Europe/Sofia', 'Europe/Tallinn', 'Europe/Tirane', 'Europe/Ulyanovsk', 'Europe/Vienna', 'Europe/Vilnius', 'Europe/Volgograd', 'Europe/Warsaw', 'Europe/Zurich', 'Antarctica/Macquarie', 'Australia/Adelaide', 'Australia/Brisbane', 'Australia/Broken_Hill', 'Australia/Darwin', 'Australia/Eucla', 'Australia/Hobart', 'Australia/Lindeman', 'Australia/Lord_Howe', 'Australia/Melbourne', 'Australia/Perth', 'Australia/Sydney', 'Pacific/Apia', 'Pacific/Auckland', 'Pacific/Bougainville', 'Pacific/Chatham', 'Pacific/Efate', 'Pacific/Fakaofo', 'Pacific/Fiji', 'Pacific/Gambier', 'Pacific/Guadalcanal', 'Pacific/Guam', 'Pacific/Kanton', 'Pacific/Kiritimati', 'Pacific/Kosrae', 'Pacific/Kwajalein', 'Pacific/Marquesas', 'Pacific/Nauru', 'Pacific/Niue', 'Pacific/Norfolk', 'Pacific/Noumea', 'Pacific/Pago_Pago', 'Pacific/Palau', 'Pacific/Pitcairn', 'Pacific/Port_Moresby', 'Pacific/Rarotonga', 'Pacific/Tahiti', 'Pacific/Tarawa', 'Pacific/Tongatapu', 'Asia/Almaty', 'Asia/Amman', 'Asia/Aqtau', 'Mangghystaū/Mankistau', 'Asia/Aqtobe', 'Aqtöbe/Aktobe', 'Asia/Ashgabat', 'Asia/Atyrau', "Atyraū/Atirau/Gur'yev", 'Asia/Baghdad', 'Asia/Baku', 'Asia/Bangkok', 'Asia/Beirut', 'Asia/Bishkek', 'Asia/Choibalsan', 'Asia/Colombo', 'Asia/Damascus', 'Asia/Dhaka', 'Asia/Dili', 'Asia/Dubai', 'Asia/Dushanbe', 'Asia/Famagusta', 'Asia/Gaza', 'Asia/Hebron', 'Asia/Ho_Chi_Minh', 'Asia/Hong_Kong', 'Asia/Hovd', 'Asia/Jakarta', 'Asia/Jayapura', 'New Guinea (West Papua / Irian Jaya), Malukus/Moluccas', 'Asia/Jerusalem', 'Asia/Kabul', 'Asia/Karachi', 'Asia/Kathmandu', 'Asia/Kolkata', 'Asia/Kuching', 'Asia/Macau', 'Asia/Makassar', 'Asia/Manila', 'Asia/Nicosia', 'Asia/Oral', 'Asia/Pontianak', 'Asia/Pyongyang', 'Asia/Qatar', 'Asia/Qostanay', 'Qostanay/Kostanay/Kustanay', 'Asia/Qyzylorda', 'Qyzylorda/Kyzylorda/Kzyl-Orda', 'Asia/Riyadh', 'Asia/Samarkand', 'Asia/Seoul', 'Asia/Shanghai', 'Asia/Singapore', 'Asia/Taipei', 'Asia/Tashkent', 'Asia/Tbilisi', 'Asia/Tehran', 'Asia/Thimphu', 'Asia/Tokyo', 'Asia/Ulaanbaatar', 'Asia/Urumqi', 'Asia/Yangon', 'Asia/Yerevan', 'Indian/Chagos', 'Indian/Maldives', 'Antarctica/Casey', 'Antarctica/Davis', 'Antarctica/Mawson', 'Antarctica/Rothera', 'Antarctica/Troll', 'Antarctica/Vostok', 'Africa/Abidjan', 'Africa/Algiers', 'Africa/Bissau', 'Africa/Cairo', 'Africa/Casablanca', 'Africa/El_Aaiun', 'Africa/Johannesburg', 'Africa/Juba', 'Africa/Khartoum', 'Africa/Lagos', 'Africa/Maputo', 'Africa/Monrovia', 'Africa/Nairobi', 'Africa/Ndjamena', 'Africa/Sao_Tome', 'Africa/Tripoli', 'Africa/Tunis', 'Africa/Windhoek', 'Atlantic/Cape_Verde', 'Indian/Mauritius']
months = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
month_map = { "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6, "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12}
months_short = [ "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
days = list(range(1, 32))

def time_to_emoji(time_str):
    time_to_emoji_map = { "00:00": ":clock12:", "00:30": ":clock1230:", "01:00": ":clock1:", "01:30": ":clock130:", "02:00": ":clock2:", "02:30": ":clock230:", "03:00": ":clock3:", "03:30": ":clock330:", "04:00": ":clock4:", "04:30": ":clock430:", "05:00": ":clock5:", "05:30": ":clock530:", "06:00": ":clock6:", "06:30": ":clock630:", "07:00": ":clock7:", "07:30": ":clock730:", "08:00": ":clock8:", "08:30": ":clock830:", "09:00": ":clock9:", "09:30": ":clock930:", "10:00": ":clock10:", "10:30": ":clock1030:", "11:00": ":clock11:", "11:30": ":clock1130:", "12:00": ":clock12:", "12:30": ":clock1230:", "13:00": ":clock1:", "13:30": ":clock130:", "14:00": ":clock2:", "14:30": ":clock230:", "15:00": ":clock3:", "15:30": ":clock330:", "16:00": ":clock4:", "16:30": ":clock430:", "17:00": ":clock5:", "17:30": ":clock530:", "18:00": ":clock6:", "18:30": ":clock630:", "19:00": ":clock7:", "19:30": ":clock730:", "20:00": ":clock8:", "20:30": ":clock830:", "21:00": ":clock9:", "21:30": ":clock930:", "22:00": ":clock10:", "22:30": ":clock1030:", "23:00": ":clock11:", "23:30": ":clock1130:", }
    return time_to_emoji_map.get(time_str)
    
async def setup(bot): 
    pass