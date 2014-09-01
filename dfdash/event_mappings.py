from collections import namedtuple
import re

EventMapping = namedtuple("EventMapping", "pattern types")

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
