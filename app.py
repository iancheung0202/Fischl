import discord, os, firebase_admin, datetime, time, asyncio, random, logging, sys
from discord.ui import Button, View
from discord.ext import commands
from firebase_admin import credentials, db
from commands.Tickets.tickets import CloseTicketButton, TicketAdminButtons, ConfirmCloseTicketButtons, CreateTicketButtonView, DownloadTranscriptFromLog
from commands.Tickets.tickets import SelectView as ticketselection
from commands.Help.help import HelpPanel
from partnership.partnership import PartnerView, PartnershipView, ConfirmView, SelectView
from partnership.nopingpartnership import PartnerView as pv
from partnership.nopingpartnership import PartnershipView as prv
from partnership.nopingpartnership import ConfirmView as cv
from partnership.nopingpartnership import SelectView as sv
# from commands.CafeOnly.staff import ApplyForStaff, AcceptRejectButton
from commands.CafeOnly.staff import RefreshStaffView, RefreshStaffViewTT
from commands.CafeOnly.admin import ServerLeaveButton, LeaksAccess, LeaksAccessTT
# from commands.CafeOnly.vcmoderator import ApplyForVCMod, AcceptRejectButtonForVCMod
from commands.CafeOnly.team import TeamSelectionButtons, RefreshTeamStats, Defend, MalaiseDefend, TimeSlotsView, QuotaDefend, SabotageDefend, ReverbDefend, BreachDefend, ShadowRealmDefend, CollapseDefend
from commands.onMemberJoin import WelcomeBtnView
from commands.CafeOnly.customCommands import BuildPanel
from commands.Utility.dm import Reply
from commands.Utility.massdm import MassReply
from commands.CoOp.coOp import CoOpButtonView, CoOpView, CoOpClaimedView
#from commands.CoOp.characterSupportHSR import CharSuppButtonView, CharSuppView, CharSuppClaimedView
from commands.CoOp.coOpSystem import CoOpButtonViewSystem
from commands.CoOp.coOpSystem import CoOpView as CoOpViewSYSTEM
from commands.CoOp.coOpSystem import CoOpClaimedView as CoOpClaimedViewSYSTEM
# from commands.Utility.buy import ConfirmPurchaseView
# from commands.Utility.mora import ConfirmView
# from commands.CafeOnly.guessvoice import Submit

cred = credentials.Certificate("./assets/fischl-beta-firebase-adminsdk-pir1k-798a85c249.json")
# fischl-beta-firebase-adminsdk-pir1k-798a85c249
# fischl-backup-firebase-adminsdk-wq5ya-e31d81e586
default_app = firebase_admin.initialize_app(cred, {
	'databaseURL':"https://fischl-beta-default-rtdb.firebaseio.com"
})

allCharacters = ['Albedo', 'Alhaitham', 'Aloy', 'Amber', 'Arlecchino', 'Ayaka', 'Ayato', 'Baizhu', 'Barbara', 'Beidou', 'Bennett', 'Candace', 'Charlotte', 'Chevreuse', 'Chiori', 'Chongyun', 'Collei', 'Cyno', 'Dehya', 'Diluc', 'Diona', 'Dori', 'Eula', 'Faruzan', 'Fischl', 'Freminet', 'Furina', 'Gaming', 'Ganyu', 'Gorou', 'Heizou', 'Hu Tao', 'Itto', 'Jean', 'Kaeya', 'Kaveh', 'Kazuha', 'Keqing', 'Kirara', 'Klee', 'Kokomi', 'Layla', 'Lisa', 'Lynette', 'Lyney', 'Mika', 'Mona', 'Nahida', 'Navia', 'Neuvillette', 'Nilou', 'Ningguang', 'Noelle', 'Qiqi', 'Raiden Shogun', 'Razor', 'Rosaria', 'Kujou Sara', 'Sayu', 'Shenhe', 'Shinobu', 'Sucrose', 'Tartaglia', 'Thoma', 'Tighnari', 'Venti', 'Wanderer', 'Wriothesley', 'Xiangling', 'Xianyun', 'Xiao', 'Xingqiu', 'Xinyan', 'Yae Miko', 'Yanfei', 'Yaoyao', 'Yelan', 'Yoimiya', 'Yun Jin', 'Zhongli']

character_lines = {
  "Albedo": "Happy birthday, USER. You look especially happy, would you mind if I sketched you? The capacity of our brains is limited, so we are bound to forget things. But when an image is transferred onto paper or canvas, the sketch becomes an extension of our memory. We can remember that past feeling when we later look at the sketch.",
  "Alhaitham": "Happy birthday, USER. I've always thought people are a little too enthusiastic about celebrating the day they were born. Wouldn't it be better to apply all that enthusiasm towards their daily lives and improve their standards of living? But you seem to have done well for yourself. I didn't know what kind of gift to get, so I'll just set up a special application channel, reserved for your submissions alone.",
  "Aloy": "Never put much stock in birthdays. Where I come from, it's a time to celebrate your mother, not yourself. Even so, I wish you a, uh... happy day, USER.",
  "Amber": "Hey, happy birthday, USER! Here, I have a gift for you: an exclusive, custom-made version of Baron Bunny that I sewed for you myself. Uh... don't worry, \"custom-made\" means that it won't explode!",
  "Arlecchino": "This memo states that today is your birthday. Is that true? Birthdays should be lively occasions. It's always nice to have an excuse to set formal matters aside every now and then, whether it's for the purpose of celebrating yourself or others. Come, USER. I've prepared a feast for you at the House of the Hearth. Let's not keep the children waiting.",
  "Ayaka": "Come with me! We're not going far away — I promise it won't delay you too much.\nI managed to find out when your birthday was well in advance, USER, so I could prepare in good time. Hopefully this wasn't assuming too much, but I guessed you might prefer this to an expensive gift.\nIn honor of your birthday, please allow me to perform a fan dance for you.",
  "Ayato": "Happy Birthday, USER! Now, how would you like to be Yashiro Commissioner for a day, hmm? All the work has been handled already, so you can focus on simply enjoying the feeling of having an enormous amount of executive power at your fingertips. Don't worry, the retainers won't dare question it, I'll be with you the entire time, hehe.",
  "Baizhu": "I hope that this day will be one filled with joy every year, and that you would always keep these times near. Happy Birthday, Traveler USER!",
  "Barbara": "Here you go! This is the gift I got for your birthday, USER, along with my exclusive autograph! Hehe, when my next song comes out, I'll make sure you're the first one to hear it! Happy birthday, USER!",
  "Beidou": "Come, board my ship. I've gathered the crew. The food and drink are all prepared. Today is your birthday, USER, so you are the captain. Haha, so: where should we set sail?",
  "Bennett": "Happy birthday, USER! Best of luck in the year ahead. Don't worry, bad luck isn't contagious! As long as I'm around, it'll be drawn to me and not you, so you're safe.",
  "Candace": "Happy birthday, USER! It's amazing to think that you were born on this day, years ago in the past. Do you have a birthday wish? If it involves going somewhere dangerous, let me join you — I'll be your guard. Or if you're looking to rest and revitalize, come to Aaru Village, and I'll serve you the finest meats and drinks we have.",
  "Charlotte": "Happy Birthday, USER! Did you read today's Steambird yet? I put a birthday greeting in there for you, hehe... Wait, you still haven't bought a copy? No problem, I picked one up before leaving the office. Look — here it is! I fought pretty hard to get it on this page.",
  "Chevreuse": "Happy Birthday, USER! Ahem... At attention! Chin up, shoulders back! Let's take your measurements... I want to commission a smaller, more portable musket and holster for you...\nOkay, at ease. While the musket is being commissioned, you need to log some hours at the shooting range first. No time like the present! Follow me!",
  "Chiori": "Yeah, yeah... Happy birthday, or whatever, USER. Just tell me if there's a gift you like — I can't be bothered to try and guess what you want. Hm? Too direct? Alright then, why don't you grab Navia, Kirara, and the others, and maybe a few of your friends as well. We can have a party tonight at my place. I'll take some notes on the gifts that the others have prepared for you, and make you an accessory right then and there. Ten thousand mora that you'd like it. Haha, call it the confidence of the owner of Chioriya Boutique.",
  "Chongyun": "On the anniversary of your birth, please accept this gift of a flower, made of ice crystals. I carved it myself. If you ever encounter an evil spirit, cast this toward it — the spell I have cast upon it will immediately come into effect and hopefully get you out alive. Also... Happy birthday, USER.",
  "Collei": "Uh, H—Happy Birthday, USER! Here's the cake I made for you, and here are the candles, so yeah... Amber said in her letter that this would do the job... Oh! And, and here's the gift I got for you!\n...I'm sorry, I don't have much experience arranging birthday parties. I have no idea if you'll like it... Aah, I'm getting all flustered now. If anything's not how you like it, please say, and I'll make absolutely sure to plan a nicer birthday celebration for you next year!",
  "Cyno": "Ahem... I'd like to wish you a happy birthday, USER. Though I don't have much experience with celebrations, once I realized your birthday was coming, I decided to make some preparations. First, I have this deck for you that I worked on for a few days, I think it'll really suit your style. Also, I adjusted my schedule to open up some time, so is there anywhere you'd like to go? I'd be happy to accompany you. A birthday only lasts a day, but you should take the chance to really enjoy it. Just make sure we can be back within three days.",
  "Dehya": "Happy Birthday, USER! Reach into your pocket, your present's already in there. How'd I do it? Hehe, just a little trick of the trade. Anyway, more importantly, I've booked us a real feast at Lambad's Tavern, so let's get ourselves over there! ...Huh? Oh, don't worry, I didn't invite any of the other mercs. Nah, that rowdy bunch is always getting into arguments — not the kind of people you'd want at a birthday celebration. It'll just be me and you, like it should be... Ahem, c'mon, c'mon, let's go.",
  "Diluc": "Happy birthday, USER. This is an important day for you. So tell me, what is it you wish for? If it is within my power to bestow it upon you, I will give it my consideration.",
  "Diona": "Here you go — fried fish with my special sauce! ... Relax, USER, I didn't add anything strange! My cooking is actually really good when I want it to be — stop talking and try it already! Hmph... that's better... Oh, and uh, happy birthday, USER.",
  "Dori": "Today I can grant you one wish, USER! After all, I am the great and almighty Dori! Go on, tell me, what do you wish for? But lemme just tell you now that a lifetime supply of Mora is off the table.",
  "Eula": "Today is a day worth observing, though you shouldn't mark your development in age alone, USER. Accept my gift of a bone whistle, and allow me to teach you its secrets. When your day of reckoning comes, see how long you can fend me off with it... It'll make the whole thing much more exciting.",
  "Faruzan": "Happy birthday, USER! Here's a small toy for you. It's an assembly of a number of miniature puzzle mechanisms — you can find a button and lever here, as well as a roller to the side. Just play with it however you want, and I'll take care of it if it breaks. Hmph, and don't think I'm treating you like a child. Everyone, regardless of age, could use a moment of happiness and relaxation.",
  "Fischl": "Well! If today is truly the anniversary of your birth, it shan't do for me not to mark the occasion. USER, you have my full attention. Speak! Speak to me of your wishes, that which you most desire to fulfill during your fleeting and harsh existence in this wretched world. Whatever that wish may be.",
  "Freminet": "Would you be willing to come with me somewhere, USER? There's this place I know where the scenery is spectacular. I think it's even more magical than a fantasy novel. I have a secret hideout there, and I keep some glowing sea creatures as pets... I just want to give you a birthday experience like you've never had before, and then give you my birthday wishes... Will you give me the chance to do that, USER?",
  "Furina": "Happy Birthday, USER! Here, please take this ticket as your gift. It's a VIP seat to see Happy Day, just don't forget to show up to the performance! Hmm? What's \"Happy Day\"? *sigh* Well, I wanted to keep it a surprise... But it's an opera that I've rehearsed personally. It's about a big group of people that gather together to celebrate a certain very important person. You understand now, right? Just don't forget to come!",
  "Gaming": "So a little birdie told me that it's your birthday today, USER... When were you planning on telling me? Tsk... Anyway, I went ahead and made a reservation at Xinyue Kiosk. Eight dishes, a soup, and as much rice as you can eat, with Longevity Buns and Tong Sui for dessert. Plus I invited all your friends along. Uh, and I also put together a little birthday wushou dance for you — nothing extravagant, just a bit of fun really — but yeah, I hope you like it!",
  "Ganyu": "Many happy returns, USER! After all the times you've looked out for me, I didn't even remember to get you a gift — whoops! Silly me, I... What's that behind my back? Ah. You saw it then. It's a failed attempt at making a Qingxin Flower cake... I wanted it to be perfect, but... Oh, you think it tastes good? Do you really?",
  "Gorou": "Today's a momentous occasion, your birthday, USER! Allow me to arrange all the celebrations for you! We can make a bonfire on the beach and catch some fresh fish and crabs. I'll personally prepare a morale-boosting meal that would make even the highest-ranking generals jealous.",
  "Heizou": "USER, after I learned that today was your birthday, there was a brief moment when I really wanted to take you to a locked room chock-full of mechanisms and gifts, where you could only get out by solving all the puzzles... Hehe, it's actually really fun! You know, of course I wouldn't do anything like that unless I was sure you'd actually enjoy it. Here, come with me. There's this beautiful scenic spot I've gotta show you before the sun goes down.",
  "Hu Tao": "Tonight the stars are dazzling and the moon majestic, it must be a special day... But just what day could it be... Haha, I know, I know! It's your birthday, USER! It really is a great day.",
  "Itto": "Today's an important day. I had to send the gang away, otherwise they'd be accusing me of favoritism. Here, take a look at this. I got you the greatest birthday gift combo ever, USER! One top-grade Onikabuto — I'll have you know it took me three whole days and nights to catch this bad boy — one out-of-print collectible trading card that took me 300 rounds to get my hands on, and finally, a birthday song performance performed personally by yours truly! Happy Birthday to you, Happy Birthday to you, Happy Biiiirthday dear Traveler, Happy Birthday to youuuu, USER!",
  "Jean": "Today is a day worth celebrating. If you must ask why, well, let me remind you that today is when you, the one who is blessed by the wind, came into the world. Since this is your birthday, I'll allow you to take it easy.\nAhem... ♪ Happy birthday to you, USER... ♪\nUh... Please forgive my presumptuousness. I hope this gift is to your liking.",
  "Kaeya": "Today is a day worth celebrating, I hope this day can bring you true happiness, USER.",
  "Kaveh": "Is it your birthday today, USER? Well, congratulations! Birthdays are important days, and it's also one of those days in the year that gets you thinking about your family. However you spend today, I hope it makes you happy.",
  "Kazuha": "I heard it was your birthday, USER, so I wrote a haiku for you. Unfortunately, I'm not the most talented in this area, and after trying for several evenings, I was still only able to come up with the first two lines... I guess I'll just share what I've got so far, then. \"Sun and moon rejoice / Birds of dawn sing songs anew\"... Wait, don't say a word, I think the final line is coming to me... Yes, how about.... \"Far from home, with you.\" Anyway, Happy Birthday. Let's go and get you some cake, shall we?",
  "Keqing": "Happy birthday, USER! I've got a very special gift for you. It might look like an ordinary old lantern, but this one runs on Electro energy and stays alight for a really long time. For those times when you need a little extra light in your life.",
  "Kirara": "Happy birthday, USER! It doesn't matter if you're a human or a youkai, coming into this world is always worth celebrating! If you want, I can take you to the place I grew up in. It's not bustling with people, and it's not all that interesting, but it always makes me feel relaxed. Oh, and I'll let you sleep inside my favorite box, too! Having a nap inside it always feels great!",
  "Klee": "♪ Happy birthday to you, happy birthday to you, happy birthday dear traveler, happy birthday to you, USER! ♪ You're older than me right? That means you've had way more birthdays than me... I'm sooo jealous!",
  "Kokomi": "Happy birthday, USER! So, what are your plans for the day? Oh, why don't we celebrate on Watatsumi Island? First, I'll take you out at daybreak to see the sunrise, then we can go diving during the heat of the day. In the evening, we can go for a stroll around Sangonomiya Shrine. If it rains, we'll find somewhere cozy to hide out with a few strategy books, and try to bake a cake together! In any case, no need to plan anything, the grand strategist has everything thought out for you!",
  "Layla": "Happy birthday, USER. I got you this pocket astrolabe... The same stars witness the fate of the human race today as did yesterday, and as will forever. May they cast their gaze upon you, and may they stay with you always, through the desert and across the ocean, until you reach your destination.",
  "Lisa": "Here, take this amulet, it will bring you good luck. It's my birthday gift to you, USER. I spent a long time making it, so don't lose it now!",
  "Lynette": "Happy Birthday, USER! Let me give you this card... it's not a greeting card, so of course nothing's written on it. Write down what kind of present you want, place it in my hat, and no matter what it might be, you'll get it.",
  "Lyney": "I have a feather here, just an ordinary feather... Go ahead, you can hold it and see for yourself. Ready? And... boom! It was a party popper all along. Happy Birthday, USER! See this? I caught one of the paper streamers floating down. Now, make a wish and picture a birthday gift in your mind's eye as I light it. Three... two... one... Great! Verrry good, I know exactly what you were thinking now. The last step, put your hand inside my hat... Well? Is it the gift you wanted?",
  "Mika": "Oh, what should we do for an occasion like this? Hmm... Today is your most special day, USER, so we should really live it up! I've prepared \"A Tour of Mondstadt's Most Stunning Spots.\" It contains information on lots of beautiful locations that are hardly known to anyone else. I wish you happiness every day until this day arrives again next year.",
  "Mona": "Happy Birthday, USER. Here's my gift to you — it's a bag containing some words of advice that may help you through tough patches.\n...No, don't open it yet. During the year ahead, this bag will open itself when the right time comes.",
  "Nahida": "I was thinking, USER, that your birthday celebration needs to be at least as grand as the Sabzeruz Festival, so... Hmm? Too much? But everyone's already done preparing for it. C'mon, c'mon, USER, let's go! Just this once — I'll make sure you love it!",
  "Navia": "Do you believe that wishes can come true? You know, like when you toss a coin into a fountain for good luck? As long as you throw enough coins in, one of your wishes is sure to come true, right?\nWell anyway, today's your birthday, USER, so I'm not leaving anything to chance — I've got a whole bag of Mora here dedicated to making your birthday wish come true. Whatever you want, I'll do everything in my power to make it happen!",
  "Neuvillette": "Ah, so it's your birthday. Happy birthday, USER. I do not know if rain is in the forecast today, but let me see what I can do.",
  "Nilou": "Umm... Happy birthday, USER! I learned a new dance, and I want to show it to you. Uh, am I nervous? *sigh* You saw right through me. It's because... I wanted to incorporate my feelings into the moves, but then the choreography just got more and more difficult... Anyway, I just wish that your life will always be full of wonder and happiness.",
  "Ningguang": "These are some of Liyue's finest brocades, woven from silk flowers. This one is for you, USER, and I hope that you'll like it. I wish you a happy birthday.",
  "Noelle": "Since you're always so busy adventuring, there must be so many little things you never get round to, surely? Well, you need not worry about them adding up, because today, I am all yours — your exclusive maid for the entire day! Just leave it all to me, USER! ...Also, I'd like to take this opportunity to wish you a very happy birthday!",
  "Qiqi": "Many happy returns, USER. Here is a bag of herbal medicine for you. You must be very surprised that I remembered? Let me explain. Last time you told me, I wrote your birthday down on a piece of paper. If I look at something once a day, it eventually goes into my long-term memory, and it will stay there forever.",
  "Raiden Shogun": "Happy birthday, USER! Let's celebrate together and make it a moment to remember for the whole year until your next birthday celebration, and so on and so forth. Then, you shall have an eternity of happiness.",
  "Razor": "Today is your day, USER. You were born on this day, many moons ago. I want to make you happy today. Can we eat meat together?",
  "Rosaria": "Today's your birthday, USER, so if you have any dirty work that needs taking care of, I can give you a hand... Just don't tell anybody, got it?",
  "Sara": "Excellent timing, USER. I will dispense with the formalities and get straight to the point — do you have a birthday wish? Providing that it does not conflict with the Almighty Shogun's grand cause, I will make every effort to see it come to fruition. To show that I am being completely serious, I will allow you to make not one, but five birthday wishes.",
  "Sayu": "Wanna learn some ninja skills, USER? I can teach you! Well, only the skills I know, of course. Hmm? Why aren't I asleep? ...Uhh, because I'm not sleepy... and also because today is a special day! I had to stay awake today so I'd have the chance to say it to you in person: Happy Birthday, USER.",
  "Shenhe": "I've been told that birthdays are important occasions for most people. They give presents to celebrate the anniversary of the other person's birth. Material possessions aren't really my thing, but... The view of the starry night sky in the mountains is the most beautiful thing I've ever seen in my life. I've frozen this lake and turned it into a mirror, so you can appreciate the reflection of the fleeting clouds and distant stars right up close. This is my way of celebrating your birthday, USER... Hope you like it.",
  "Shinobu": "Happy birthday, USER! Here, take this special dart made from Naku Weed. Be careful, yep, that's the way to hold it... Make sure you predict the trajectory before you throw it... Hehe, I'm happy that you like it. Oh, don't treat it like a toy, it's still quite dangerous. If you want to practice a little more, I can teach you.",
  "Sucrose": "Happy birthday, USER! I've been running experiments for months, and finally I can give you this potion. It will allow you to relive your most beautiful memories of the past year. I call it \"Bio-Potion No. 3916.\" Huh? No, no, not 3196, it's 3916!",
  "Tartaglia": "Happy birthday, comrade USER! Anyone you need knocked off their perch today? Let me know. I'll happily oblige...",
  "Thoma": "Quick, USER, come with me! I remembered it's your birthday, obviously, so I thought I'd throw you a proper party. There's food, there's drinks, and I invited a whole bunch of your friends, too. Hey, this is your birthday we're talking about! I wasn't about to let you spend it all alone!",
  "Tighnari": "Happy birthday, USER! I picked out a potted plant in full bloom for you, along with a gardening guide. If anything happens to it, don't hesitate to find me at any time. This plant comes with a Forest Watcher lifetime guarantee.\nI'll have you know a lot of flowers are in season on your birthday. It took me forever to choose one. I'll get you a different species next year!",
  "Venti": "Someone once told me you're supposed to eat a cake on your birthday... Tada! Here's your birthday cake, USER — it's apple flavored! And here's a spoon. The cake didn't rise properly in the oven, that's why it looks more akin to an apple pie... Ugh, baking is really quite complicated!",
  "Wanderer": "USER, give me your hand. Heh, there's no need to be nervous. I'm just taking you to a vantage point.\nHow is it? The scenery here should be quite breathtaking. There's no need to thank me — I see little point in it.",
  "Wriothesley": "Our tradition says that all children of Fontaine are born amid their parents' wishes and blessings, but I'd like to think that all children are born from such wonderful feelings. Anything that I can say to celebrate your birth would feel a little trivial next to that, right, USER?\nUnfortunately, I won't be able to reduce your prison sentence if you were to commit a crime — the only thing I would be able to pull off would be a special Welfare Meal for your birthday dinner. With all that in mind, why don't you try to respect the law a bit more around your birthday, so we'll be able to celebrate somewhere nice on the surface?",
  "Xiangling": "Ah, USER, there you are! Come with me, I've prepared a birthday feast all for you! ... No really, USER, I insist! Which dish is your favorite? It's okay, take your time, try them all first, then let me know!",
  "Xianyun": "Here, USER, open this wooden box. It's a miniature mechanical person for your recreational enjoyment. Try playing with it. Observe — if you clap the hands like this, the lotus petals open, the colored lights turn on one set at a time, and then a melody plays. It is that birthday tune that the young and hip of this generation enjoy so much. Certain to add a touch of merriment and levity to your birthday feast... Have a wonderful day.",
  "Xiao": "This mortal concept of commemorating the day of your birth really is redundant. Wait, USER. Have this. It's a butterfly I made from leaves.\nOkay. Take it, USER. It's an adepti amulet — it staves off evil.",
  "Xingqiu": "May this day of your birth be filled with much mirth, USER!\nAccording to historical records, Tiancheng's stone bridge was formed by a fallen rock spear thrown by the Geo Archon Morax in battle. If you walk along the bridge on your birthday and throw some Mora into the sea from both sides, you will be blessed in the coming year... \nUSER, your birthday only comes once a year, so be quick about it if you wanna go... I'm not kidding, it's true! Go try it and you'll see!",
  "Xinyan": "Happy birthday, USER! I made some embroidery especially for you. Check it out — I sewed both our images on in the style of Fontaine's dolls. Pretty cute, eh? ...Why are you looking at me like that? Wh—What, it's not that weird that I can do embroidery!",
  "Yae Miko": "Ah, so today is your birthday, USER... \"On your ceremonious reckoning of years, I task my kin with seeing to it that that which you seek, you shall surely find, and that that for which your heart longs, you shall surely receive. Remain pure of heart and true of spirit, and their protection shall be bestowed on you.\" There you go. May all go well in your year ahead, and may all your wishes be fulfilled. Are we done?",
  "Yanfei": "Happy birthday, USER! Here, this is for you. I've collated legislation from all the nations — you're planning to go traveling, right? It will serve you well to familiarize yourself with the law of the different lands.\nDon't study too hard mind you, or else... I won't be of any use to you.",
  "Yaoyao": "This is the day of your birth, USER! And as is tradition, this calls for a bowl of longevity noodles. I got Xiangling to teach me how to make it, and I managed to put all the noodles in the water without breaking a single one! I also put a big plump egg in there, hee-hee! Come on, USER, let's go, you've got to eat it before it goes cold. Wishing you a happy, healthy birthday and a long and prosperous life.",
  "Yelan": "If I was to tell you that maybe you shouldn't celebrate too hard today, because you'll let your guard down, and someone out there might just be waiting for that moment to make their move on you... it probably wouldn't go down very well. So USER, relax and take it easy today. Oh, and you should stop by the Yanshang Teahouse — I whipped up some treats especially for you. Not sweet ones, of course. Just the tiniest little hint of chili.",
  "Yoimiya": "Birthdays are never occasions for yourself alone, USER. Those who send you cakes, light candles, applaud, and cheer... They are all truly thankful that you were born into this world. That's why it must be a lively occasion, so that everyone can get their chance to thank you! Well then — happy birthday! Are you ready? I'm about to ignite the fireworks!",
  "Yun Jin": "Oh, USER, so today's your birthday? Well, I wouldn't know how to throw you a feast if I tried... so how about I sing you a song? For you alone, an audience of one. So... what song would you like to hear me sing? The choice is yours.",
  "Zhongli": "Happy birthday, USER. This is a dried Glaze Lily that came into bloom on the day of your birth. Long ago, the people of Liyue would say that this flower blooms bearing the weight of the beautiful memories and prayers of the land. I believe this to have been applied on the day you were born as well.",
}

async def char_name_to_icon(char_name):
    CHAR_NAME = char_name.replace(' ', '').capitalize() if ' ' not in char_name else char_name.split()[0] + char_name.split()[1].lower()
    return f"https://enka.network/ui/UI_AvatarIcon_{CHAR_NAME}.png"
      
class Fischl(commands.Bot):

  def __init__(self):
    super().__init__(
      command_prefix = "-",
      intents = discord.Intents.all(),
      application_id = 732422232273584198,
      help_command=None
    )

  async def setup_hook(self):
    for path, subdirs, files in os.walk('commands'):
      for name in files:
        if name.endswith('.py'):
          extension = os.path.join(path, name).replace("/", ".")[:-3]
          await self.load_extension(extension)
          print(f"Loaded {extension} in {self.user}")
    await bot.tree.sync()
    
    self.add_view(CoOpButtonView())
    self.add_view(CoOpView())
    self.add_view(CoOpClaimedView())
    #self.add_view(CharSuppButtonView())
    #self.add_view(CharSuppView())
    #self.add_view(CharSuppClaimedView())
    self.add_view(CoOpButtonViewSystem())
    self.add_view(CoOpViewSYSTEM())
    self.add_view(CoOpClaimedViewSYSTEM())
    self.add_view(CloseTicketButton())
    self.add_view(TicketAdminButtons())
    self.add_view(LeaksAccess())
    self.add_view(LeaksAccessTT())
    self.add_view(ConfirmCloseTicketButtons())
    self.add_view(RefreshTeamStats())
    self.add_view(CreateTicketButtonView())
    self.add_view(ticketselection())
    list = await bot.tree.fetch_commands()
    self.add_view(HelpPanel(list))
    self.add_view(PartnerView())
    self.add_view(DownloadTranscriptFromLog())
    self.add_view(PartnershipView())
    self.add_view(ConfirmView())
    self.add_view(SelectView())
    self.add_view(Reply())
    self.add_view(MassReply())
    self.add_view(pv())
    self.add_view(prv())
    self.add_view(ServerLeaveButton())
    self.add_view(cv())
    self.add_view(sv())
    self.add_view(Defend())
    self.add_view(MalaiseDefend())
    self.add_view(QuotaDefend())
    self.add_view(SabotageDefend())
    self.add_view(ReverbDefend())
    self.add_view(BreachDefend())
    self.add_view(CollapseDefend())
    self.add_view(ShadowRealmDefend())
    self.add_view(TimeSlotsView())
    self.add_view(BuildPanel())
    # self.add_view(ApplyForStaff())
    # self.add_view(AcceptRejectButton())
    # self.add_view(Submit())
    # self.add_view(ApplyForVCMod())
    # self.add_view(AcceptRejectButtonForVCMod())
    self.add_view(TeamSelectionButtons())
    # self.add_view(JanTeamChallenge())
    self.add_view(WelcomeBtnView())
    # self.add_view(ConfirmPurchaseView())
    self.add_view(ConfirmView())
    self.add_view(RefreshStaffView())
    self.add_view(RefreshStaffViewTT())
    
  async def logging(self):
    logging.Formatter.converter = time.gmtime
    formatter = logging.Formatter(
      '%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler = logging.FileHandler('console_output.log')
    file_handler.setLevel(logging.INFO)  # Set the file logging level
    file_handler.setFormatter(formatter)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)  # Set the console logging level
    console_handler.setFormatter(formatter)
    logging.basicConfig(level=logging.INFO, handlers=[file_handler, console_handler])
    
    class PrintLogger:
      def __init__(self):
        self.stdout = sys.stdout
      def write(self, message):
        if message.strip():
          logging.info(message.strip())
      def flush(self):
        pass

    sys.stdout = PrintLogger()

    def log_uncaught_exceptions(exc_type, exc_value, exc_traceback):
      if issubclass(exc_type, KeyboardInterrupt):
        # Don't log keyboard interruptions
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
      logging.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

    sys.excepthook = log_uncaught_exceptions

  async def status_task(self):
    timeout = 5
    while True:
      await asyncio.sleep(timeout)
      await self.change_presence(status=discord.Status.dnd, activity=discord.Activity(type=discord.ActivityType.playing, name="Genshin Impact"))
      await asyncio.sleep(timeout)
      await self.change_presence(status=discord.Status.idle, activity=discord.Activity(type=discord.ActivityType.watching, name=f"over {len(self.users)} users"))
      await asyncio.sleep(timeout)
      await self.change_presence(status=discord.Status.online, activity=discord.Activity(type=discord.ActivityType.listening, name="Hoyo's Cafe"))
      await asyncio.sleep(timeout)
      await self.change_presence(status=discord.Status.dnd, activity=discord.Activity(type=discord.ActivityType.listening, name=f"{len(self.guilds)} guilds"))
      await asyncio.sleep(timeout)
    
  async def mansion_protector(self):
    while True:
      current_time = datetime.datetime.utcnow()
      if current_time.hour == 0 and current_time.minute == 0:
        server = self.get_guild(717029019270381578)
        role = server.get_role(1200241691798536345)
        teams = {
          "Team Mondstadt": 1083867546962370730,
          "Team Liyue": 1083867653803888722,
          "Team Inazuma": 1083867759982682183,
          "Team Sumeru": 1083867870200602734,
          "Team Fontaine": 1106654299582386310,
        }
        for member in role.members:
          team = teamchn = None
          for role in member.roles:
            if "team" in role.name.lower() and "art" not in role.name.lower() and "event" not in role.name.lower():
              team = role
              teamchn = teams[role.name]
          if team is not None and teamchn is not None:
            embed = discord.Embed(title=":alarm_clock: It's that time of the day!", description="You are able to get daily resources for your team again!", color=team.color)
            button = Button(style=discord.ButtonStyle.link, label="Your Team Channel",  url=f"https://discord.com/channels/717029019270381578/{teamchn}")
            view = View()
            view.add_item(button)
          try:
            await member.send(embed=embed, view=view)
          except Exception:
            pass
        await asyncio.sleep(60)
        continue
      await asyncio.sleep(20)
    
  async def birthday(self):
    while True:
      current_time = datetime.datetime.now(datetime.timezone.utc)
      minutes_to_test = [0, 15, 30, 45]
      if current_time.minute in minutes_to_test:
        ref = db.reference("/Birthday")
        bday = ref.get()
        ref2 = db.reference("/Birthday System")
        bs = ref2.get()
        for key, value in bday.items(): # For each birthday entry
          for k, v in bs.items(): # For each server having birthday enabled
            server = self.get_guild(v['Server ID'])
            if server is None:
              continue
            birthday_role = server.get_role(v['Role ID'])
            display_utc_date = value["Display UTC Date"]
            try:
              utc_date_object = datetime.datetime.strptime(display_utc_date, "%m-%d %H:%M")
            except ValueError as e:
              continue
            if (utc_date_object.month == current_time.month and utc_date_object.day == current_time.day and utc_date_object.hour == current_time.hour and utc_date_object.minute == current_time.minute): # Fetched some birthday
              member = server.get_member(value["User ID"])
              if member is None: # Member left server
                #db.reference('/Birthday').child(key).delete()
                print(f"Member left server - birthday {value['User ID']}")
                continue
              print("Fetched some birthday")
              character = value["Fav Character"]
              footer = ""
              if character == "None":
                character = random.choice(allCharacters)
                footer = "Use \"/birthday set\" to update your birthday with timezones & favorite character!"
              icon_link = await char_name_to_icon(character)
              webhook = await self.fetch_webhook(v['Webhook ID'])
              embed = discord.Embed(description=f"{character_lines[character].replace('USER', f'**{member.name}**')}", color=discord.Colour.random())
              embed.set_footer(text=footer)
              msg = await webhook.send(content=f":birthday: Happy birthday to {member.mention}! Enjoy your special day!", embed=embed, username=character, avatar_url=icon_link, wait=True)
              await msg.add_reaction("🎂")
              await msg.create_thread(name=f"Wish {member.name} a happy birthday!")
              await member.add_roles(birthday_role)
              try:
                button = Button(style=discord.ButtonStyle.link, label=f"Read {character}'s Message", url=f"{msg.jump_url}")
                view = View()
                view.add_item(button)
                await member.send(f"Happy birthday, {member.mention}! **{server.name}** and its staff team wishes you a fantastic day. May your special day be as amazing as you are! 🎉🎂🥳\n\n*PS: **{character}** has something to say to you... :eyes:*", view=view)
              except Exception as e:
                print("Cannot send happy birthday DM to member")
            elif (utc_date_object.month == current_time.month and utc_date_object.day == current_time.day):
              pass # Still their birthday!
            else:
              removeRole = False
              for member in birthday_role.members:
                if value["User ID"] == member.id:
                  removeRole = True
                  break
              if removeRole:
                await server.get_member(value["User ID"]).remove_roles(birthday_role)
            
        await asyncio.sleep(60)
        continue
      await asyncio.sleep(20)

  async def on_ready(self):
    print(f'{self.user} has connected to Discord!')
    self.loop.create_task(self.status_task())
    self.loop.create_task(self.mansion_protector())
    self.loop.create_task(self.birthday())
    self.loop.create_task(self.logging())
    ref = db.reference('/Uptime')
    status = ref.get()
    for key, value in status.items():
      db.reference('/Uptime').child(key).delete()
      break
    new = int(float(time.mktime(datetime.datetime.now().timetuple())))
    data = {
      "asdadad": {
        "Uptime": new,
      }
    }
    for key, value in data.items():
      ref.push().set(value)
    chn = self.get_channel(1036314355169513482)
    embed = discord.Embed(title="✅ Bot Online", description=f"**Date:** <t:{new}:D>\n**Time:** <t:{new}:t>\n\n**Servers in:** {len(self.guilds)}\n**Discord Version:** {discord.__version__}", colour=0x7BE81B)
    embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
    await chn.send(embed=embed)

bot = Fischl()

##############################################################
##############################################################
##############################################################
##############################################################

class FischlBeta(commands.Bot):

  def __init__(self):
    super().__init__(
      command_prefix = "-",
      intents = discord.Intents.all(),
      application_id = 1033190899229929542,
      help_command=None
    )

  async def setup_hook(self):
    for path, subdirs, files in os.walk('commands'):
      for name in files:
        if name.endswith('.py'):
          extension = os.path.join(path, name).replace("/", ".")[:-3]
          await self.load_extension(extension)
          print(f"Loaded {extension} in {self.user}")
            
    for path, subdirs, files in os.walk('betaCommands'):
      for name in files:
        if name.endswith('.py'):
          extension = os.path.join(path, name).replace("/", ".")[:-3]
          await self.load_extension(extension)
          print(f"Loaded {extension} in {self.user}")
    await beta.tree.sync()

  async def status_task(self):
    timeout = 5
    while True:
      await asyncio.sleep(timeout)
      await self.change_presence(status=discord.Status.dnd, activity=discord.Activity(type=discord.ActivityType.playing, name="Genshin Impact"))
      await asyncio.sleep(timeout)
      await self.change_presence(status=discord.Status.idle, activity=discord.Activity(type=discord.ActivityType.watching, name=f"over {len(self.users)} users"))
      await asyncio.sleep(timeout)
      await self.change_presence(status=discord.Status.online, activity=discord.Activity(type=discord.ActivityType.listening, name="Hoyo's Cafe"))
      await asyncio.sleep(timeout)
      await self.change_presence(status=discord.Status.dnd, activity=discord.Activity(type=discord.ActivityType.listening, name=f"{len(self.guilds)} guilds"))
      await asyncio.sleep(timeout)

  async def on_ready(self):
    print(f'{self.user} has connected to Discord!')
    self.loop.create_task(self.status_task())
    chn = self.get_channel(1036314355169513482)
    embed = discord.Embed(title="✅ Bot Online", description=f"**Date:** <t:{new}:D>\n**Time:** <t:{new}:t>\n\n**Servers in:** {len(self.guilds)}\n**Discord Version:** {discord.__version__}", colour=0x7BE81B)
    embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
    await chn.send(embed=embed)

beta = FischlBeta()

bot.run(TOKEN)