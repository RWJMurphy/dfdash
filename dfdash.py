#!/usr/bin/env python
from __future__ import print_function, unicode_literals

import codecs
from collections import namedtuple
import json
import functools
import os
import os.path
import random
import re
import sqlite3
import threading
import time

from watchdog.events import FileSystemEvent, FileSystemEventHandler
# from watchdog.observers import Observer
from watchdog.observers.polling import PollingObserver

EventMapping = namedtuple("EventMapping", "pattern types")


class DFDash:
    LOGFILE_NAME = "gamelog.txt"
    DB_NAME = "DFDash.db"

    class EventHandler(FileSystemEventHandler):
        def __init__(self, on_modified, db_connector):
            self._db_connector = db_connector
            self._db_lock = threading.Lock()
            self._on_modified = on_modified

        def on_modified(self, event):
            self._db_lock.acquire()
            db = self._db_connector()
            self._on_modified(event, db)
            db.close()
            self._db_lock.release()

    EVENT_IGNORE = map(re.compile,
        [
            #".*",
            ".+ STARTING NEW GAME .+",
            "Generating world.+",
            "\sSeed:.+",
            "\sHistory Seed:.+",
            "\sName Seed:.+",
            "\sCreature Seed:.+",
            ".+ Starting New Outpost .+",
            ".+ Loading Fortress .+",
        ])
    # consider something faster, e.g. https://code.google.com/p/esmre/
    EVENT_MAPPINGS = map(
        lambda (pattern, types): EventMapping(re.compile(pattern), types),
        [
            # damage
            ("(?P<origin>.+) (?P<attack>(bashes|gouges|kicks|punches|pushes|strikes)) (?P<target>.+) in the (?P<body_part>.+) with (his|her|its) (?P<weapon>.+), (?P<wound>(bruising|shattering)) the (?P<material>.+)( through the .+)!",
                ["mob.\g<origin>.combat.\g<weapon>.\g<attack>.\g<target>.\g<body_part>",
                 "mob.\g<target>.health.\g<body_part>.\g<material>.\g<wound>"]),
            ("(?P<origin>.+) (?P<attack>(bites|scratches|shakes|stings|snatches at)) (?P<target>.+) (around by|in) the (?P<body_part>.+), (?P<wound>.+) the (?P<material>.+)( through the .+)!",
                 ["mob.\g<origin>.combat.\g<attack>.\g<target>.\g<body_part>",
                  "mob.\g<target>.health.\g<body_part>.\g<material>.\g<wound>"]),
            # sever
            ("(?P<origin>.+) (?P<attack>(bashes|gouges|kicks|punches|pushes|strikes)) (?P<target>.+) in the (?P<body_part>.+) with (his|her|its) (?P<weapon>.+), and the severed part sails off in an arc!",
                ["mob.\g<origin>.combat.\g<weapon>.\g<attack>.\g<target>.\g<body_part>",
                 "mob.\g<target>.health.\g<body_part>.destroyed.severed"]),
            ("(?P<origin>.+) (?P<attack>(bites|scratches|shakes|stings|snatches at)) (?P<target>.+) (around by|in) the (?P<body_part>.+) and the severed part sails off in an arc!",
                 ["mob.\g<origin>.combat.\g<attack>.\g<target>.\g<body_part>",
                  "mob.\g<target>.health.\g<body_part>.destroyed.severed"]),
            # collapse
            ("(?P<origin>.+) (?P<attack>(bashes|gouges|kicks|punches|pushes|strikes)) (?P<target>.+) in the (?P<body_part>.+) with (his|her|its) (?P<weapon>.+) and the injured part collapses( into a lump of gore)?!",
                ["mob.\g<origin>.combat.\g<weapon>.\g<attack>.\g<target>.\g<body_part>",
                 "mob.\g<target>.health.\g<body_part>.destroyed.collapsed"]),
            ("(?P<origin>.+) (?P<attack>(bites|scratches|shakes|stings|snatches at)) (?P<target>.+) (around by|in) the (?P<body_part>.+) and the(( injured)? part|.+) collapses( into a lump of gore)?!",
                 ["mob.\g<origin>.combat.\g<attack>.\g<target>.\g<body_part>",
                  "mob.\g<target>.health.\g<body_part>.destroyed.collapsed"]),
            # split
            ("(?P<origin>.+) (?P<attack>(bashes|gouges|kicks|punches|pushes|strikes)) (?P<target>.+)'s (?P<body_part>.+) with (his|her|its|.+'s) (?P<weapon>.+) and the( injured)? part splits in gore!",
                 ["mob.\g<origin>.combat.\g<weapon>.\g<attack>.\g<target>.\g<body_part>",
                  "mob.\g<target>.health.\g<body_part>.destroyed.split"]),
            ("(?P<origin>.+) (?P<attack>(bashes|gouges|kicks|punches|pushes|strikes)) (?P<target>.+) in the (?P<body_part>.+) with (his|her|its|.+'s) (?P<weapon>.+) and the( injured)? part splits in gore!",
                 ["mob.\g<origin>.combat.\g<weapon>.\g<attack>.\g<target>.\g<body_part>",
                  "mob.\g<target>.health.\g<body_part>.destroyed.split"]),
            # explode
            ("(?P<origin>.+) (?P<attack>(bashes|gouges|kicks|punches|pushes|strikes)) (?P<target>.+) in the (?P<body_part>.+) with (his|her|its) (?P<weapon>.+) and the injured part explodes into gore!",
                 ["mob.\g<origin>.combat.\g<weapon>.\g<attack>.\g<target>.\g<body_part>",
                  "mob.\g<target>.health.\g<body_part>.destroyed.exploded"]),
            # smashed into body
            ("(?P<origin>.+) (?P<attack>(bashes|gouges|kicks|punches|pushes|strikes)) (?P<target>.+) in the (?P<body_part>.+) with (his|her|its) (?P<weapon>.+) and the( injured)? part is smashed into the body, an unrecognizable mass!",
                 ["mob.\g<origin>.combat.\g<weapon>.\g<attack>.\g<target>.\g<body_part>",
                  "mob.\g<target>.health.\g<body_part>.destroyed.smashed"]),
            # shredded
            ("(?P<origin>.+) (?P<attack>(bashes|gouges|kicks|punches|pushes|strikes)) (?P<target>.+) in the (?P<body_part>.+) with (his|her|its) (?P<weapon>.+) and the( injured)? part is ripped into loose shreds!",
                 ["mob.\g<origin>.combat.\g<weapon>.\g<attack>.\g<target>.\g<body_part>",
                  "mob.\g<target>.health.\g<body_part>.destroyed.shredded"]),
            ("(?P<origin>.+) (?P<attack>(bites|scratches|shakes|stings|snatches at)) (?P<target>.+) (around by|in) the (?P<body_part>.+) and the( injured)? part is ripped into loose shreds!",
                 ["mob.\g<origin>.combat.\g<attack>.\g<target>.\g<body_part>",
                  "mob.\g<target>.health.\g<body_part>.destroyed.shredded"]),
            # torn apart
            ("(?P<origin>.+) (?P<attack>(bashes|gouges|kicks|punches|pushes|strikes)) (?P<target>.+)'s (?P<body_part>.+) with (his|her|its|.+) (?P<weapon>.+), tearing it apart!",
                 ["mob.\g<origin>.combat.\g<weapon>.\g<attack>.\g<target>.\g<body_part>",
                  "mob.\g<target>.health.\g<body_part>.destroyed.torn_apart"]),
            ("(?P<origin>.+) (?P<attack>(bites|scratches|shakes|stings|snatches at)) (?P<target>.+)'s (?P<body_part>.+), tearing it apart!",
                 ["mob.\g<origin>.combat.\g<weapon>.\g<attack>.\g<target>.\g<body_part>",
                  "mob.\g<target>.health.\g<body_part>.destroyed.torn_apart"]),
            ("(?P<origin>.+) (?P<attack>(bashes|gouges|kicks|punches|pushes|strikes)) (?P<target>.+) in the (?P<body_part>.+) with (his|her|its) (?P<weapon>.+) and the( injured)? part is torn apart!",
                 ["mob.\g<origin>.combat.\g<attack>.\g<target>.\g<body_part>",
                  "mob.\g<target>.health.\g<body_part>.destroyed.torn_apart"]),
            ("(?P<origin>.+) (?P<attack>(bites|scratches|shakes|stings|snatches at)) (?P<target>.+) (around by|in) the (?P<body_part>.+) and the( injured)? part is torn apart!",
                 ["mob.\g<origin>.combat.\g<attack>.\g<target>.\g<body_part>",
                  "mob.\g<target>.health.\g<body_part>.destroyed.torn_apart"]),

            # projectiles
            ("The flying (?P<weapon>.+) strikes (?P<target>.+) in the (?P<body_part>.+), (?P<wound>.+) the (?P<material>.+)!",
                ["mob.\g<target>.health.\g<body_part>.\g<material>.\g<wound>",
                 "global.combat.projectile.\g<weapon>.strikes.\g<target>"]),
            ("(?P<origin>.+) jumps away from The flying (?P<weapon>.+)!",
                 ["mob.\g<origin>.combat.dodge.\g<weapon>"]),

            # other weapon stuff
            ("The (?P<weapon>.+) has lodged firmly in the wound!",
              "global.combat.\g<weapon>.lodged"),

            # wrestling
            ("(?P<origin>.+) grabs (?P<target>.+) by the (?P<body_part>.+) with (his|her|its) (?P<weapon>.+)!",
                "mob.\g<origin>.combat.wrestling.\g<weapon>.grab.\g<target>.\g<body_part>"),
            ("(?P<origin>.+) latches on firmly!", "mob.\g<origin>.combat.wrestling.latched_on"),
            ("(?P<origin>.+) releases the grip of (.+)'s (?P<weapon>.+) (from|on) (?P<target>.+)'s (?P<body_part>.+).",
                "mob.\g<origin>.combat.wrestling.\g<weapon>.release.\g<target>.\g<body_part>"),
            ("(?P<origin>.+) breaks the grip of (?P<target>.+)'s (?P<weapon>.+) on (.+)'s (?P<body_part>.+).",
                ["mob.\g<origin>.combat.wrestling.\g<body_part>.break_grip.\g<target>.\g<weapon>",
                 "mob.\g<origin>.combat.wrestling.\g<weapon>.release.\g<target>.\g<body_part>"]),
            ("(?P<origin>.+) is unable to break the grip of (?P<target>.+)'s (?P<weapon>.+) on (.+)'s (?P<body_part>.+)!",
                "mob.\g<origin>.combat.wrestling.\g<body_part>.break_grip.\g<target>.\g<weapon>.failed"),
            ("(?P<origin>.+) throws (?P<target>.+) by the (?P<body_part>.+) with (his|her|its|.+'s) (?P<weapon>.+)!",
                 ["mob.\g<origin>.combat.wrestling.\g<weapon>.throw.\g<target>.\g<body_part>"
                  "mob.\g<target>.status.flying"]),
            ("(?P<origin>.+) takes (?P<target>.+) down by the (?P<body_part>.+) with (his|her|its|.+'s) (?P<weapon>.+)!",
                 "mob.\g<origin>.combat.wrestling.\g<weapon>.take_down.\g<target>.\g<body_part>"),
            ("(?P<origin>.+) places a chokehold on (?P<target>.+)'s (?P<body_part>.+) with (his|her|its|.+'s) (?P<weapon>.+)!",
                 ["mob.\g<origin>.combat.wrestling.\g<weapon>.choke.\g<target>.\g<body_part>",
                  "mob.\g<target>.health.\g<body_part>.choked"]),
            ("(?P<origin>.+) strangles (?P<target>.+)'s (?P<body_part>.+), (?P<wound>.+) the (?P<material>.+)!",
                 ["mob.\g<origin>.combat.wrestling.strangle.\g<target>.\g<body_part>",
                  "mob.\g<target>.health.\g<body_part>.\g<material>.\g<wound>"]),
            ("(?P<origin>.+) strangles (?P<target>.+)'s (?P<body_part>.+)!",
                 "mob.\g<origin>.combat.wrestling.strangle.\g<target>.\g<body_part>"),
            ("(?P<origin>.+) locks (?P<target>.+)'s (?P<body_part>.+) with (his|her|its|.+'s) (?P<weapon>.+)!",
                 "mob.\g<origin>.combat.wrestling.\g<weapon>.lock.\g<target>.\g<body_part>"),
            ("(?P<origin>.+) bends (?P<target>.+)'s (?P<body_part>.+) with (his|her|its|.+'s) (?P<weapon>.+) and the (.+) collapses!",
                ["mob.\g<origin>.combat.wrestling.\g<weapon>.lock.\g<target>.\g<body_part>",
                 "mob.\g<target>.health.\g<body_part>.collapsed"]),
            ("(?P<origin>.+) releases the joint lock of (.+)'s (?P<weapon>.+) on (?P<target>.+)'s (?P<body_part>.+)\.",
                "mob.\g<origin>.combat.wrestling.\g<weapon>.lock.\g<target>.\g<body_part>.release"),

            # enraged
            ("(?P<origin>.+) has become enraged!", "mob.\g<origin>.status.enraged"),
            # charge
            ("(?P<origin>.+) charges at (?P<target>.+)!", "mob.\g<origin>.combat.charge.\g<target>"),
            ("(?P<origin>.+) collides with (?P<target>.+)!", "mob.\g<origin>.combat.collide.\g<target>"),
            ("(?P<origin>.+) is knocked over( and tumbles backward)?!", "mob.\g<origin>.status.prone"),
            # interrupted
            ("(?P<origin>.+)'s attack is interrupted!", "mob.\g<origin>.combat.miss"),
            # missed
            ("(?P<origin>.+) misses (?P<target>.+)!", "mob.\g<origin>.combat.miss.\g<target>"),
            # glances away
            ("(?P<origin>.+) (?P<attack>(bashes|gouges|kicks|punches|pushes|strikes)) (?P<target>.+) in the (?P<body_part>.+) with (his|her|its) (?P<weapon>.+), but the attack glances away!",
                 ["mob.\g<origin>.combat.\g<weapon>.\g<attack>.\g<target>.\g<body_part>",
                  "mob.\g<origin>.combat.miss.\g<target>.glanced_away"]),
            # deflected
            ("(?P<origin>.+) (?P<attack>(bashes|gouges|kicks|punches|pushes|strikes)) (?P<target>.+) in the (?P<body_part>.+) with (his|her|its) (?P<weapon>.+), but the attack is deflected by .+'s (?P<armor>.+)!",
             ["mob.\g<origin>.combat.\g<weapon>.\g<attack>.\g<target>.\g<body_part>",
              "mob.\g<target>.combat.\g<armor>.deflect.\g<origin>.\g<weapon>"]),
            # batted aside
            ("(?P<origin>.+) bats the spinning (?P<attack>.+) aside with the (?P<weapon>.+)!",
                "mob.\g<origin>.combat.\g<weapon>.bat.\g<attack>"),
            # training attack
            ("(?P<origin>.+) (?P<attack>(bashes|gouges|kicks|punches|pushes|strikes)) (?P<target>.+) in the (?P<body_part>.+) with (his|her|its) (?P<weapon>.+), lightly tapping the target!",
             "mob.\g<origin>.combat.\g<weapon>.training.\g<attack>.\g<target>.\g<body_part>"),

            ("(?P<origin>.+) attacks (?P<target>.+) but (She|He|They|It) rolls away!",
                 ["mob.\g<origin>.combat.miss.\g<target>",
                  "mob.\g<target>.combat.dodge.\g<origin>.attack"]),
            ("(?P<origin>.{,20}) jumps away!",
                "mob.\g<origin>.combat.dodge.unknown.attack"),
            ("(?P<origin>.+) attacks (?P<target>.+) but (She|He|They|It) jumps away!",
                ["mob.\g<origin>.combat.miss.\g<target>",
                 "mob.\g<target>.combat.dodge.\g<target>.attack"]),
            ("(?P<origin>.+) jumps out of (?P<weapon>.+)'s flight path!",
                 ["mob.\g<origin>.combat.dodge.\g<weapon>"]),

            # special attacks
            # web
            ("(?P<origin>.+) shoots out thick strands of webbing!", "mob.\g<origin>.combat.chot_web"),
            # venom
            ("(?P<material>.+) is injected into (?P<target>.+)'s (?P<body_part>.+)!",
                "mob.\g<target>.health.\g<body_part>.injected_with.\g<material>"),
            # cloud
            # caught in
            ("(?P<target>.+) is caught in a (cloud|burst) of (?P<origin>.+)'s (?P<material>.+)!",
                ["mob.\g<origin>.combat.cloud.\g<material>.caught.\g<target>",
                 "mob.\g<target>.health.caught_in.\g<origin>.\g<material>"]),
            # breathes
            ("(?P<target>.+) breathes a (cloud|burst) of (?P<origin>.+)'s (?P<material>.+)!",
                ["mob.\g<origin>.combat.cloud.\g<material>.inhaled.\g<target>",
                 "mob.\g<target>.health.inhaled.\g<origin>.\g<material>"]),

            # inventory
            ("(?P<origin>.+) loses hold of the (?P<item>.+)\.", "mob.\g<origin>.dropped.\g<item>"),

            # health
            ("(?P<origin>.+) is propelled away by the force of the blow!", "mob.\g<origin>.status.flying"),
            ("(?P<origin>.+) slams into an obstacle!",
                ["mob.\g<origin>.combat.slammed_into_obstacle",
                 "mob.\g<origin>.status.flying.cancel"]),
            ("(?P<origin>.+)'s (?P<body_part>.+) takes the full force of the impact, (?P<wound>(bruising|shattering)) the (?P<material>.+)!",
                 "mob.\g<origin>.health.\g<body_part>.\g<material>.\g<wound>"),
            ("(?P<origin>.+)'s (?P<body_part>.+) skids along the ground, (?P<wound>.+) the (?P<material>.+)!",
                 "mob.\g<origin>.health.\g<body_part>.\g<material>.\g<wound>"),
            ("(?P<origin>.+) collapses and falls to the ground from over-exertion\.", ["mob.\g<origin>.health.collapsed", "mob.\g<origin>.status.prone"]),
            ("(?P<origin>.+) passes out from exhaustion\.", ["mob.\g<origin>.status.unconscious", "mob.\g<origin>.status.prone"]),
            ("(?P<origin>.+) gives in to pain.", ["mob.\g<origin>.status.unconscious", "mob.\g<origin>.status.prone"]),
            ("(?P<origin>.+) regains consciousness.", "mob.\g<origin>.status.unconscious.cancel"),
            ("(?P<origin>.+) is no longer stunned\.", "mob.\g<origin>.status.stun.cancel"),

            ("(?P<origin>.+) looks (?P<status>(even more )?sick)!",
                 "mob.\g<origin>.health.\g<status>"),
            ("(?P<origin>.+) (?P<action>retches|vomits)\.",
                 "mob.\g<origin>.health.\g<action>"),
            ("(?P<origin>.+) is having( more)? trouble breathing!",
                "mob.\g<origin>.health.suffocating"),

            ("(?P<origin>.+) is caught up in the web!", "mob.\g<origin>.status.webbed"),
            ("(?P<origin>.+) is partially free of the web.", "mob.\g<origin>.status.webbed.escaping"),
            ("(?P<origin>.+) is completely free of the web.", "mob.\g<origin>.status.webbed.cancel"),
            ("(?P<origin>.+) falls over\.", "mob.\g<origin>.status.prone"),
            ("(?P<origin>.+) stands up\.", "mob.\g<origin>.status.prone.cancel"),


            # global
            ("An? (?P<material>(artery|ligament|(motor )?nerve|tendon)) in the (?P<body_part>.+) has been (?P<damage>.+)( by the attack)?!", "global.health.\g<body_part>.\g<material>.\g<damage>"),
            ("An? (?P<material>(artery|ligament|(motor )?nerve|tendon)) has been (?P<damage>.+)( by the attack)?!", "global.health.unknown.\g<material>.\g<damage>"),
            ("Many (?P<material>(artery|ligament|(motor )?nerve|tendon)s) have been (?P<damage>.+)( by the attack)?!", "global.health.unknown.\g<material>.\g<damage>.severe"),
            #("(?P<origin>.+) (?P<attack>(bashes|gouges|kicks|punches|pushes|strikes)) (?P<target>.+) in the (?P<body_part>.+), but the attack is deflected by .+'s (?P<armor>.+)!",
                 #["global.combat.\g<origin>.\g<attack>.\g<target>.\g<body_part>",
                 # "mob.\g<target>.combat.\g<armor>.deflect.global.\g<origin>"]),

            ("(?P<origin>.+): (?P<speech>(I cannot just stand by\.  I will have my revenge\.))", "mob.\g<origin>.speech.\g<speech>"),

            # Death
            ("(?P<origin>.+) has drowned\.", "mob.\g<origin>.health.death.drowning"),
            ("(?P<origin>.+) has died (of|from) thirst\.", "mob.\g<origin>.health.death.dehydration"),
            ("(?P<origin>.+) has starved to death\.", "mob.\g<origin>.health.death.starvation"),
            ("(?P<origin>.+) has been struck down\.", "mob.\g<origin>.health.death.struck_down"),
            ("(?P<origin>.+) has been crushed by a drawbridge\.", "mob.\g<origin>.health.death.drawbridge"),
            ("(?P<origin>.+) has died after colliding with an obstacle\.", "mob.\g<origin>.health.death.collision"),
            ("(?P<origin>.+) slams into an obstacle and blows apart!", "mob.\g<origin>.health.death.collision.hard"),
            ("(?P<origin>.+) has bled to death\.", "mob.\g<origin>.health.death.bled_out"),
            ("(?P<origin>.+) has died of old age\.", "mob.\g<origin>.health.death.age"),
            ("(?P<origin>.+) has suffocated\.", "mob.\g<origin>.health.death.suffocation"),
            ("(?P<origin>.+) has been encased in ice\.", "mob.\g<origin>.health.death.encased.ice"),
            ("(?P<origin>.+) has been encased in cooling lava\.", "mob.\g<origin>.health.death.encased.obsidian"),
            ("(?P<origin>.+) has been shot and killed\.", "mob.\g<origin>.health.death.shot"),
            ("(?P<origin>.+) has succumbed to infection\.", "mob.\g<origin>.health.death.infection"),
            ("(?P<origin>.+) has been impaled on spikes\.", "mob.\g<origin>.health.death.spikes"),
            ("(?P<origin>.+) has killed by a flying object\.", "mob.\g<origin>.health.death.ufo_impact"),
            ("(?P<origin>.+) has been killed by a trap\.", "mob.\g<origin>.health.death.trap"),
            ("(?P<origin>.+) has been murdered by (.+)!", "mob.\g<origin>.health.death.murder"),
            ("(?P<origin>.+) has been scared to death by the (.+)!", "mob.\g<origin>.health.death.fright"),

            # Death - Found
            ("(?P<origin>.+) has been found dead\.", "mob.\g<origin>.health.death.other"),
            ("(?P<origin>.+) has been found dead, dehydrated\.", "mob.\g<origin>.health.death.dehydration"),
            ("(?P<origin>.+) has been found, starved to death\.", "mob.\g<origin>.health.death.starvation"),
            ("(?P<origin>.+) has been found dead, badly crushed\.", "mob.\g<origin>.health.death.crushing"),
            ("(?P<origin>.+) has been found dead, drowned\.", "mob.\g<origin>.health.death.drowning"),
            ("(?P<origin>.+) has been found dead, completely drained of blood!", "mob.\g<origin>.health.death.vampire"),
            ("(?P<origin>.+) has been found dead, contorted in fear!", "mob.\g<origin>.health.death.fright"),

            # Profession
            ("(?P<origin>.+) has become a (?P<class>.+).", "mob.\g<origin>.profession.\g<class>"),
            # Animal
            ("(?P<origin>.+) has been slaughtered\.", "mob.\g<origin>.health.death.butchered"),
            ("(?P<origin>.+) has given birth to (.+)\.", "mob.\g<origin>.birth"),
            ("(?P<origin>An animal) has become a Stray (?P<class>war|hunting) (?P<species>.+)\.", "global.animal.\g<species>.trained.\g<class>"),
            ("(?P<origin>.+) has grown to become a (?P<class>.+).", "mob.\g<origin>.grown.\g<class>"),

            # Lazy Partying Urists
            ("(?P<origin>.+) has organized a party at (?P<target>.+).",
                "mob.\g<origin>.party.\g<target>"),
            # Trade / Diplomacy
            ("The outpost liaison (?P<origin>.+) from (?P<civilization>.+) has arrived\.", "civilization.\g<civilization>.liason.\g<origin>.arrived"),
            ("An?( elven)? caravan from (?P<origin>.+) has arrived\.", "civilization.\g<origin>.merchant.arrived"),
            ("Merchants have arrived and are unloading their goods\.", "global.merchant.unloading"),
            ("Their wagons have bypassed your inaccessible site\.", "global.merchant.caravan.bypassed"),
            ("The merchants need a trade depot to unload their goods\.", "global.merchant.bypassed"),
            ("The merchants from (?P<origin>.+) will be leaving soon\.", "civilization.\g<origin>.merchant.departing"),
            ("The merchants from (?P<origin>.+) have embarked on their journey\.", "civilization.\g<origin>.merchant.departed"),

            ("Some migrants have arrived.", "global.migrants_arrived"),

            # Job Management
            ("(?P<origin>.+) cancels (?P<job>.+): (?P<reason>.+)\.", "mob.\g<origin>.job.\g<job>.cancelled"),
            ("(?P<job>.+) \((?P<qty>[0-9]+)\) has been completed\.", "global.job.\g<job>.complete"),
            ("The dwarves were unable to complete the (?P<job>.+)\.", "global.job.\g<job>.cancelled"),
            ("The dwarves suspended the construction of (?P<job>.+)\.", "global.job.\g<job>.suspended"),

            # Mining
            ("You have struck (?P<material>.+)!", "global.struck.\g<material>"),
            ("You have discovered an expansive cavern deep underground\.", "global.struck.cavern"),

            # Crafting
            ("(?P<prigin>.+) has been possessed!", "mob.\g<origin>.status.strange_mood.possessed"),
            ("(?P<prigin>.+) has claimed a (?P<workshop>.+).", "mob.\g<origin>.status.strange_mood.claimed.\g<workshop>"),
            ("(?P<prigin>.+) has begun a mysterious construction!", "mob.\g<origin>.status.strange_mood.construction_started"),

            ("(?P<origin>.+) has created a masterpiece (.+)!",
                "mob.\g<origin>.craft.masterpiece"),

            # Weather
            ("It has started raining\.", "weather.rain"),
            ("The weather has cleared\.", "weather.clear"),

            ("It is now summer\.", "calendar.season.summer"),
            ("Autumn has come\.", "calendar.season.autumn"),
            ("Winter is upon you\.", "calendar.season.winter"),
            ("Spring has arrived!", "calendar.season.spring"),
        ]
    )
    #random.shuffle(EVENT_MAPPINGS)

    class Event:
        @classmethod
        def from_text(cls, event_line):
            """
            :type event_line: unicode
            :rtype list[DFDash.Event]
            """
            def extract_events(text, mapping):
                """
                :type mapping: EventMapping
                """
                maybe_events = []
                try:
                    matches = mapping.pattern.match(text)
                    if matches:
                        types = mapping.types
                        if not isinstance(types, (list, tuple)):
                            types = [types, ]
                        for event_type in types:
                            try:
                                origin = matches.group('origin')
                                event_type = matches.expand(event_type)
                            except IndexError:
                                origin = "unknown"
                                event_type = matches.expand(re.sub('\\\\g<origin>', origin, event_type))
                            except Exception as e:
                                print("Error expanding template:")
                                print(matches.groups())
                                print(event_type)
                                raise
                            maybe_events.append(
                                DFDash.Event(origin=origin, message=text,
                                             event_type=event_type))
                except Exception as e:
                    print("Error testing regex:")
                    print(mapping.pattern.pattern)
                    print(text)
                    raise
                return maybe_events

            events = []
            for maybe_events in map(
                    functools.partial(extract_events, event_line),
                    DFDash.EVENT_MAPPINGS):
                if maybe_events is not None:
                    for event in maybe_events:
                            events.append(event)
            if events:
                if len(events) > 2:
                    print("Got many events for line:")
                    print("\t{}".format(event_line))
                    for e in events:
                        print("\t{}".format(e.event_type))

                return events
            for pattern in DFDash.EVENT_IGNORE:
                if pattern.match(event_line):
                    return []
            #raise Exception("Unhandled event: {}".format(event_line))
            return [DFDash.Event.unknown_event(event_line)]

        def __init__(self, origin, message, event_type):
            """
            :type origin: unicode
            :type message: unicode
            :type event_type: unicode
            """
            self.origin = origin
            self.message = message
            self.event_type = event_type

        def put(self, db, commit=False):
            """
            :type db: DFDash.DB
            """
            return db.execute(
                b"INSERT INTO events (message, type, json) VALUES (?, ?, ?)",
                ("", self.event_type, ""),
                #(self.message, self.event_type, self.json),
                commit)

        @property
        def json(self):
            return json.dumps({
                "origin": self.origin,
                "message": self.message,
                "type": self.event_type,
            })

        @classmethod
        def unknown_event(cls, event_line):
            return DFDash.Event(message=event_line, event_type="_.unknown", origin="")

    class DB:
        SCHEMA = """CREATE TABLE IF NOT EXISTS `events` (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp INTEGER DEFAULT CURRENT_TIMESTAMP,
            type TEXT,
            message TEXT,
            json TEXT
        );
        CREATE INDEX IF NOT EXISTS `idx_type` ON `events` (`type`);
        CREATE INDEX IF NOT EXISTS `idx_message` ON `events` (`message`);

        CREATE TABLE IF NOT EXISTS `dfdash_config` (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        """

        def __init__(self, db_path):
            """
            :type db_path: unicode
            """
            self._path = db_path
            self._db = sqlite3.connect(db_path)
            self._db.row_factory = sqlite3.Row

        def ensure_db_initialized(self):
            try:
                self.execute(b"SELECT * FROM events LIMIT 1")
                self.execute(b"SELECT * FROM dfdash_config LIMIT 1")
            except sqlite3.OperationalError:
                self._db.executescript(DFDash.DB.SCHEMA)
                self.execute(b"SELECT * FROM events LIMIT 1")
                self.execute(b"SELECT * FROM dfdash_config LIMIT 1")

        def execute(self, query, parameters=None, commit=False):
            """
            :type query: str
            :type parameters: tuple | dict
            :rtype list[sqlite3.Row] | int
            """
            cursor = self._db.cursor()
            parameters = parameters or ()
            try:
                cursor.execute(query, parameters)
                if commit:
                    self._db.commit()
                if cursor.rowcount == -1:
                    return cursor.fetchall()
                return cursor.rowcount
            except sqlite3.Error:
                self._db.rollback()
                raise
            finally:
                cursor.close()

        def close(self):
            self._db.close()

        def config_put(self, key, value):
            return self.execute(
                b"INSERT OR REPLACE INTO `dfdash_config` VALUES (?, ?)",
                (key, value), True)

        def config_get(self, key):
            try:
                # noinspection PyPep8
                value = self.execute(
                    b"SELECT `value` FROM `dfdash_config` WHERE `key` LIKE ? LIMIT 1",
                    (key,)
                )[0]
                return value[b"value"]
            except IndexError:
                return None

    def __init__(self, df, port=8080, db=None, limit=None):
        """
        :type df: unicode
        :type port: int
        """
        self.df = df
        self.port = port
        self.limit = limit

        self._log_path = os.path.join(df, DFDash.LOGFILE_NAME)
        self._log_offset = 0
        self._observer = PollingObserver()

        self._db_lock = threading.Lock()
        self._db_path = db or os.path.join(self.df, DFDash.DB_NAME)
        if not os.path.exists(os.path.dirname(self._db_path)):
            os.makedirs(os.path.dirname(self._db_path))
        self.connect_db().ensure_db_initialized()

        self._log_file = None
        self.open_log_file()

    def run(self):
        db = self.connect_db()
        self.watch_log()
        self._on_log_change(db)
        try:
            while True:
                time.sleep(1)
        except BaseException:
            self.stop_watching_log()
            raise

    def open_log_file(self):
        print("Opening log file: {}".format(self._log_path))
        self._log_file = codecs.open(self._log_path, "r", "cp437")
        offset = self.fetch_seek()
        print("Seeking to offset {}".format(offset))
        self._log_file.seek(offset)

    def fetch_seek(self):
        self._db_lock.acquire()
        db = self.connect_db()
        offset = db.config_get("gamelog_seek")
        db.close()
        self._db_lock.release()
        if offset is None:
            offset = 0
        else:
            offset = int(offset)
        self._log_offset = offset
        return self._log_offset

    def store_seek(self, db):
        offset = self._log_offset
        print("Storing log file offset: {}k".format(offset/1024))
        db.config_put("gamelog_seek", offset)

    def stop_watching_log(self):
        self._observer.stop()
        self._observer.join()

    def connect_db(self):
        return DFDash.DB(self._db_path)

    def watch_log(self):
        self._observer.schedule(
            DFDash.EventHandler(self._on_log_event,
                                self.connect_db),
            bytes(self.df))
        self._observer.start()

    def _on_log_event(self, event, db):
        """
        :type event: FileSystemEvent
        """
        if event.is_directory:
            return
        if event.src_path != self._log_path:
            return

        event_type = event.event_type
        if event_type == "modified":
            self._on_log_change(db)

    def _on_log_change(self, db):
        last_line = None
        while True:
            line = self._log_file.readline()
            line_length = len(line)
            line = line.rstrip()
            if line == "":
                self._log_offset += line_length
                self.store_seek(db)
                break
            if re.match(r'^x[0-9]+$', line):
                if last_line is None:
                    print("Got line '{}' but last_line is None :S".format(line))
                    continue
                else:
                    #print("Got line '{}', repeating last line".format(line))
                    line = last_line
            events = DFDash.Event.from_text(line)
            for event in events:
                commit = False
                if self.limit is not None and self.limit % COMMIT_EVERY == 0:
                    print(event.json)
                    commit = True
                event.put(db, commit)
            self._log_offset += line_length
            last_line = line
            if self.limit is not None:
                self.limit -= 1
                if self.limit % COMMIT_EVERY == 0:
                    self.store_seek(db)
                    print("{}...".format(self.limit))
                if self.limit == 0:
                    self.store_seek(db)
                    raise KeyboardInterrupt
        self.store_seek(db)

DF_PATH = r'\\BELGAER\Games\Dwarf Fortress\Dwarf Fortress 40_05 Starter Pack r2\Dwarf Fortress 0.40.05'
DB_PATH = os.path.join(os.environ['APPDATA'], "DFDash", "dfdash.db")
PROFILE = True
COMMIT_EVERY = 5000

if __name__ == "__main__":
    dfdash = DFDash(os.path.normpath(DF_PATH), db=DB_PATH)
    dfdash.run()
