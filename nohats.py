from vdf import load, dump
from os.path import abspath, exists, dirname, join
from sys import argv, stdout, stderr
from shutil import copyfile
from os import makedirs, listdir
from kvlist import KVList
from mdl import MDL
from pcf import PCF
from wave import open as wave_open
from collections import OrderedDict
from io import BytesIO
from itertools import chain

def nohats():
    with open(join(dota_dir, "scripts/items/items_game.txt"), "rb") as input:
        d = load(input)

    defaults = get_defaults(d)
    fix_models(d, defaults)
    visuals = get_visuals(d)
    visuals = filter_visuals(visuals)
    visuals = fix_style_models(d, visuals, defaults)
    visuals = fix_sounds(visuals)
    visuals = fix_hero_icons(visuals)
    visuals = fix_ability_icons(visuals)
    units = get_units()
    visuals = fix_summons(visuals, units)
    visuals = fix_hero_forms(visuals)
    visuals = fix_particle_snapshots(visuals)
    visuals = fix_couriers(visuals, units)
    visuals = fix_flying_couriers(visuals, units)
    npc_heroes = get_npc_heroes()
    visuals = fix_animations(d, visuals, npc_heroes)
    visuals = fix_particles(d, defaults, visuals, units, npc_heroes)

    x, y = filtersplit(visuals, lambda (id, k, v): not k.startswith("asset_modifier"))
    print x
    left = set()
    for e in y:
        id, k, v = e
        left.add(v.get("type"))
    print left

def get_attrib(d, item, key):
    v = item.get(key)
    if v is None and "prefab" in item:
        v = d["items_game"]["prefabs"][item["prefab"]].get(key)
    return v

def is_default(d, item):
    return get_attrib(d, item, "baseitem") == "1"

def get_hero(d, item):
    if "used_by_heroes" not in item or item["used_by_heroes"] in ["0", "1"]:
        return None
    heroes = item["used_by_heroes"].keys()
    assert len(heroes) == 1
    hero = heroes[0]
    assert item["used_by_heroes"][hero] == "1"
    return hero

def get_slot(d, item):
    return get_attrib(d, item, "item_slot")

def get_item(d, id):
    return d["items_game"]["items"][id]

def get_defaults(d):
    defaults = {}
    for id, item in d["items_game"]["items"]:
        if is_default(d, item):
            hero = get_hero(d, item)
            assert hero is not None
            slot = get_slot(d, item)
            assert slot is not None
            if (hero, slot) in defaults:
                print u"id {} is a duplicate default for {}".format(id, (hero, slot))
            else:
                defaults[(hero, slot)] = id
    return defaults

def get_default_item(d, defaults, item):
    hero = get_hero(d, item)
    slot = get_slot(d, item)
    default_id = defaults.get((hero, slot))
    if default_id is None:
        return None
    default_item = get_item(d, default_id)
    return default_item

def copy(src, dest):
    print u"copy '{}' to '{}'".format(src, dest)
    if nohats_dir is None:
        return
    src = join(dota_dir, src)
    dest = join(nohats_dir, dest)
    dest_dir = dirname(dest)
    if not exists(dest_dir):
        makedirs(dest_dir)
    copyfile(src, dest)

def copy_model(src, dest):
    assert src.endswith(".mdl")
    src = src[:-len(".mdl")]
    assert dest.endswith(".mdl")
    dest = dest[:-len(".mdl")]
    copy(src + ".mdl", dest + ".mdl")
    copy(src + ".vvd", dest + ".vvd")
    copy(src + ".dx90.vtx", dest + ".dx90.vtx")

def fix_models(d, defaults):
    for id, item in d["items_game"]["items"]:
        if id == "default" or is_default(d, item):
            continue
        if not "model_player" in item:
            continue
        if "model_player" in item:
            default_item = get_default_item(d, defaults, item)
            if default_item is not None:
                copy_model(default_item["model_player"], item["model_player"])
            else:
                copy_model("models/development/invisiblebox.mdl", item["model_player"])

def get_visuals(d):
    # get visual modifiers
    visuals = []
    for id, item in d["items_game"]["items"]:
        if id == "default" or is_default(d, item):
            continue
        if "visuals" in item:
            for k, v in item["visuals"]:
                visuals.append((id, k, v))

    return visuals

def filter_visuals(visuals):
    # particle systems are handled seperately as a group per item
    visuals = filter(lambda (id, k, v): not k.startswith("attached_particlesystem"), visuals)

    # random stuff
    visuals = filter(lambda (id, k, v): not k == "skip_model_combine", visuals)
    visuals = filter(lambda (id, k, v): not k == "skin", visuals)
    visuals = filter(lambda (id, k, v): not k == "alternate_icons", visuals)
    visuals = filter(lambda (id, k, v): not k == "animation_modifiers", visuals)

    ignore_types = ["announcer", "announcer_preview", "ability_name", "entity_scale", "hud_skin", "speech", "particle_control_point"]
    to_ignore = invisualtypes(ignore_types)
    visuals = filter(lambda x: not to_ignore(x), visuals)

    return visuals

def filtersplit(l, f):
    a = []
    b = []
    for e in l:
        if f(e):
            a.append(e)
        else:
            b.append(e)
    return (a, b)

def fix_style_models(d, visuals, defaults):
    styles_visuals, visuals = filtersplit(visuals, lambda (id, k, v): k == "styles")
    for id, _, visual in styles_visuals:
        item = get_item(d, id)
        default_item = get_default_item(d, defaults, item)
        for styleid, v in visual:
            if not "model_player" in v:
                continue
            if default_item is not None:
                copy_model(default_item["model_player"], v["model_player"])
            else:
                copy_model("models/development/invisiblebox.mdl", v["model_player"])

    return visuals

def invisualtypes(types):
    def filter(e):
        id, k, v = e
        return k.startswith("asset_modifier") and v.get("type") in types
    return filter

def isvisualtype(type):
    return invisualtypes([type])

def assetmodifier1(visual):
    type = visual.pop("type")
    asset = visual.pop("asset")
    modifier = visual.pop("modifier")
    if "frequency" in visual:
        frequency = visual.pop("frequency")
        assert frequency == "1"
    if "style" in visual:
        style = visual.pop("style")
    assert len(visual) == 0, visual.keys()
    return (asset, modifier)

def assetmodifier(iterable):
    for id, key, visual in iterable:
        yield assetmodifier1(visual)

def sound_files(sound):
    if "wave" in sound:
        return [sound["wave"].lstrip(")")]
    elif "rndwave" in sound:
        return [wave.lstrip(")") for wave in sound["rndwave"].values()]

def copy_wave(src, dest):
    print u"copy wave '{}' to '{}'".format(src, dest)
    src = join(dota_dir, src)
    try:
        input = wave_open(src, "rb")
        frames_available = input.getnframes()
        # fill to two seconds because of noise
        frames_needed = 2 * input.getframerate()
        empty_frame = "\0" * input.getsampwidth() * input.getnchannels()
        filler_frames = empty_frame * max(frames_needed - frames_available, 0)

        if nohats_dir is None:
            return
        dest = join(nohats_dir, dest)
        dest_dir = dirname(dest)
        if not exists(dest_dir):
            makedirs(dest_dir)

        try:
            output = wave_open(dest, "wb")
            output.setparams(input.getparams())
            output.writeframes(input.readframes(frames_available) + filler_frames)
        finally:
            output.close()
    finally:
        input.close()

def fix_sounds(visuals):
    # get sound list
    sounds = KVList()
    hero_sound_dir = join(dota_dir, "scripts/game_sounds_heroes")
    for filename in listdir(hero_sound_dir):
        with open(join(hero_sound_dir, filename)) as s:
            part_sounds = load(s)
        sounds.update(list(part_sounds))

    # fix sound visuals
    sound_visuals, visuals = filtersplit(visuals, isvisualtype("sound"))
    for asset, modifier in assetmodifier(sound_visuals):
        asset_files = sound_files(sounds[asset])
        modifier_files = sound_files(sounds[modifier])
        for modifier_file in modifier_files:
            copy_wave(join("sound", asset_files[0]), join("sound", modifier_file))

    return visuals

def fix_hero_icons(visuals):
    # fix hero icon visuals (lina arcana)
    icon_visuals, visuals = filtersplit(visuals, isvisualtype("icon_replacement"))
    for asset, modifier in assetmodifier(icon_visuals):
        prefix = "npc_dota_hero_"
        assert asset.startswith(prefix)
        asset = asset[len(prefix):]
        assert modifier.startswith(prefix)
        modifier = modifier[len(prefix):]
        for image_dir in ["resource/flash3/images/heroes", "resource/flash3/images/miniheroes"]:
            copy(join(image_dir, asset + ".png"), join(image_dir, modifier + ".png"))

    return visuals

def fix_ability_icons(visuals):
    # fix spell icon visuals (lina arcana)
    ability_icon_visuals, visuals = filtersplit(visuals, isvisualtype("ability_icon_replacement"))
    for asset, modifier in assetmodifier(ability_icon_visuals):
        image_dir = "resource/flash3/images/spellicons"
        copy(join(image_dir, asset + ".png"), join(image_dir, modifier + ".png"))

    return visuals

def get_units():
    # get unit model list
    with open(join(dota_dir, "scripts/npc/npc_units.txt")) as input:
        units = load(input)
    return units

def fix_summons(visuals, units):
    # fix summon overrides
    entity_model_visuals, visuals = filtersplit(visuals, isvisualtype("entity_model"))
    for asset, modifier in assetmodifier(entity_model_visuals):
        asset_model = None
        npc = units["DOTAUnits"].get(asset)
        if npc is None:
            # spirit bear
            npc = units["DOTAUnits"].get(asset + "1")
        if npc is None:
            # warlock golem
            npc = units["DOTAUnits"].get(asset + "_1")
        if npc is not None:
            asset_model = npc["Model"]
        elif asset == "dota_death_prophet_exorcism_spirit":
            # wth?
            asset_model = "models/heroes/death_prophet/death_prophet_ghost.mdl"
        assert asset_model is not None, asset
        copy_model(asset_model, modifier)

    return visuals

def fix_hero_forms(visuals):
    # fix hero model overrides
    hero_visuals, visuals = filtersplit(visuals, isvisualtype("hero_model_change"))
    for asset, modifier in assetmodifier(hero_visuals):
        copy_model(asset, modifier)

    return visuals

def fix_particle_snapshots(visuals):
    # fix particle snapshots
    psf_visuals, visuals = filtersplit(visuals, isvisualtype("particle_snapshot"))
    for asset, modifier in assetmodifier(psf_visuals):
        copy(asset, modifier)

    return visuals

def fix_couriers(visuals, units):
    courier_visuals, visuals = filtersplit(visuals, isvisualtype("courier"))
    courier_model = units["DOTAUnits"]["npc_dota_courier"]["Model"]
    for asset, modifier in assetmodifier(courier_visuals):
        assert modifier in ["radiant", "dire"]
        copy_model(courier_model, asset)
    return visuals

def fix_flying_couriers(visuals, units):
    flying_courier_visuals, visuals = filtersplit(visuals, isvisualtype("courier_flying"))
    flying_courier_model = units["DOTAUnits"]["npc_dota_flying_courier"]["Model"]
    for asset, modifier in assetmodifier(flying_courier_visuals):
        assert modifier in ["radiant", "dire"]
        copy_model(flying_courier_model, asset)

    return visuals

def get_npc_heroes():
    with open(join(dota_dir, "scripts/npc/npc_heroes.txt")) as input:
        npc_heroes = load(input)
    return npc_heroes

def fix_animations(d, visuals, npc_heroes):
    item_activities = {}
    activity_visuals, visuals = filtersplit(visuals, isvisualtype("activity"))
    for id, key, visual in activity_visuals:
        asset, modifier = assetmodifier1(visual)
        if asset == "ACT_DOTA_TAUNT":
            continue
        item = get_item(d, id)
        hero = get_hero(d, item)
        item_activities.setdefault(hero, set())
        item_activities[hero].add(modifier)

    for hero in item_activities.keys():
        model = npc_heroes["DOTAHeroes"][hero]["Model"]
        mung_offsets = set()
        model_parsed = MDL()
        with open(join(dota_dir, model), "rb") as s:
            model_parsed.unpack(s)
        for sequence in model_parsed.data["localsequence"]:
            for activitymodifier in sequence["activitymodifier"]:
                if activitymodifier["szindex"][1] in item_activities[hero]:
                    mung_offsets.add(activitymodifier["szindex"][0])

        copy(model, model)
        if nohats_dir is None:
            continue
        with open(join(nohats_dir, model), "r+b") as s:
            for offset in mung_offsets:
                s.seek(offset)
                assert s.read(1) not in ["X", ""]
                s.seek(offset)
                s.write("X")

    return visuals

def get_particlesystems(item):
    pss = []
    if item is not None:
        for key, v in item.get("visuals", []):
            if key.startswith("attached_particlesystem"):
                if v["system"] not in pss:
                    pss.append(v["system"])
    return pss

def get_particle_replacements(d, defaults, visuals):
    particle_replacements = OrderedDict()
    def add_replacement(system, default_system):
        if system in particle_replacements:
            assert particle_replacements[system] == default_system
        else:
            particle_replacements[system] = default_system

    default_particlesystems = set()
    for id, item in d["items_game"]["items"]:
        if not is_default(d, item):
            continue
        for ps in get_particlesystems(item):
            default_particlesystems.add(ps)

    for id, item in d["items_game"]["items"]:
        if id == "default" or is_default(d, item):
            continue

        default_item = get_default_item(d, defaults, item)
        pss = get_particlesystems(item)
        default_pss = get_particlesystems(default_item)
        for default_ps in list(default_pss):
            if default_ps in pss:
                default_pss.remove(default_ps)
                pss.remove(default_ps)

        while pss:
            ps = pss.pop(0)
            if ps in default_particlesystems:
                continue
            if default_pss:
                default_ps = default_pss.pop(0)
            else:
                default_ps = None
            add_replacement(ps, default_ps)

    particle_visuals, visuals = filtersplit(visuals, isvisualtype("particle"))
    for id, k, v in particle_visuals:
        asset, modifier = assetmodifier1(v)
        item = get_item(d, id)
        add_replacement(modifier, asset)

    forwarded_particle_replacements = OrderedDict()
    for system, default_system in particle_replacements.iteritems():
        while default_system in particle_replacements:
            default_system = particle_replacements[default_system]
        forwarded_particle_replacements[system] = default_system

    return visuals, forwarded_particle_replacements

def get_particle_file_systems(d, units, npc_heroes):
    files = []

    with open(join(dota_dir, "particles/particles_manifest.txt"), "rb") as s:
        l = s.readline().rstrip("\r\n")
        l = "\"" + l + "\""
        l += s.read()
    m = load(BytesIO(l))
    for k, v in m["particles_manifest"]:
        assert k == "file", k
        if v.startswith("!"):
            v = v[1:]
        files.append(v)

    for id, item in d["items_game"]["items"]:
        if "particle_file" in item and item["particle_file"] not in files:
            files.append(item["particle_file"])

    for id, item in chain(units["DOTAUnits"], npc_heroes["DOTAHeroes"]):
        if "ParticleFile" in item and item["ParticleFile"] not in files:
            files.append(item["ParticleFile"])

    particle_file_systems = {}
    for file in files:
        if not exists(join(dota_dir, file)):
            continue
        particle_file_systems[file] = []
        pcf = PCF(include_attributes=False)
        with open(join(dota_dir, file), "rb") as s:
            pcf.unpack(s)
        for e in pcf.field["elements"].data:
            if e["type"] == "DmeParticleSystemDefinition":
                if e["name"] not in particle_file_systems[file]:
                    particle_file_systems[file].append(e["name"])

    return particle_file_systems

def fix_particles(d, defaults, visuals, units, npc_heroes):
    visuals, particle_replacements = get_particle_replacements(d, defaults, visuals)

    particle_file_systems = get_particle_file_systems(d, units, npc_heroes)

    particlesystem_files = {}
    for file, systems in particle_file_systems.iteritems():
        for system in systems:
            particlesystem_files.setdefault(system, [])
            particlesystem_files[system].append(file)

    file_replacements = OrderedDict()
    for system, default_system in particle_replacements.iteritems():
        if system not in particlesystem_files:
            print >> stderr, u"Warning: system '{}' is not in any particle file".format(system)
            continue
        system_files = particlesystem_files[system]
        if default_system is None:
            default_system_files = []
        else:
            default_system_files = particlesystem_files.get(default_system, [])
            if default_system_files == []:
                if "_active" in default_system or "_passive" in default_system:
                    # pseudo-system for item triggered particle effects
                    pass
                else:
                    print >> stderr, u"Warning: default system '{}' is not in any particle file".format(default_system)

        for file in system_files:
            file_replacements.setdefault(file, OrderedDict())
            if default_system_files == []:
                file_replacements[file][system] = None
            else:
                # TODO: figure out the right choice when len(default_system_files) > 1
                file_replacements[file][system] = (default_system_files[0], default_system)

    for file, replacements in file_replacements.iteritems():
        print u"{}:".format(file)
        for system, replacement in replacements.iteritems():
            if replacement is None:
                print u"\t{} -> None".format(system)
            else:
                replacement_file, replacement_system = replacement
                print u"\t{} -> {} ({})".format(system, replacement_system, replacement_file)

    return visuals

if __name__ == "__main__":
    dota_dir = abspath(argv[1])
    try:
        nohats_dir = argv[2]
    except IndexError:
        nohats_dir = None
    if nohats_dir is not None:
        nohats_dir = abspath(nohats_dir)

    nohats()
