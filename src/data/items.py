"""DC2 item data — names extracted from CommonData, buy prices from shop scripts.

Names extracted from game memory via savestate.
Buy prices are from shop script data (not stored in CommonItemData).
Georama materials have no price in the item data structures — prices are
only loaded into CShop at runtime when entering a shop. Since the shop
isn't open during georama, we hardcode them here.
"""

# Item ID → name (extracted from CommonData via savestate)
ITEM_NAMES = {
    0x001: 'Battle Wrench', 0x002: 'Drill Wrench', 0x003: 'Smash Wrench',
    0x004: 'Stinger Wrench', 0x005: 'Poison Wrench', 0x006: 'Cubic Hammer',
    0x007: 'Digi Hammer', 0x008: 'Heavy Hammer', 0x009: 'Handy Stick',
    0x00A: 'Turkey', 0x00B: 'Swan', 0x00C: 'Flamingo',
    0x00D: 'Falcon', 0x00E: 'Albatross', 0x00F: 'Turtle Shell Hammer',
    0x010: 'Big Bucks Hammer', 0x011: 'Frozen Tuna', 0x012: "Kubera's Hand",
    0x013: 'Sigma Breaker', 0x014: 'Grade Zero', 0x015: 'LEGEND',
    0x016: 'Classic Gun', 0x017: 'Dryer Gun', 0x018: 'Trumpet Gun',
    0x019: 'Bell Trigger', 0x01A: 'Magic Gun', 0x01B: 'Soul Breaker',
    0x01C: 'Grenade Launcher', 0x01D: 'Dark Viper', 0x01E: 'Twin Buster',
    0x01F: 'Jurak Gun', 0x020: 'Question Shooter', 0x021: 'Steal Gun',
    0x022: 'Supernova', 0x023: 'Star Breaker', 0x024: 'Wild Cat',
    0x025: 'Sexy Panther', 0x026: 'Desperado', 0x027: 'Sigma Bazooka',
    0x028: 'Last Resort', 0x029: 'Long Sword', 0x02A: 'Broad Sword',
    0x02B: 'Baselard', 0x02C: 'Gladius', 0x02D: 'Wise Owl Sword',
    0x02E: 'Cliff Knife', 0x02F: 'Antique Sword', 0x030: 'Bastard Sword',
    0x031: 'Kitchen Knife', 0x032: 'Tsukikage', 0x033: 'Sun Sword',
    0x034: 'Serpent Slicer', 0x036: 'Shamshir', 0x037: 'Ama no Murakumo',
    0x038: "Lamb's Sword", 0x039: 'Dark Cloud', 0x03A: 'Brave Ark',
    0x03B: 'Big Bang', 0x03C: 'Atlamillia Sword', 0x03D: 'Mardan Sword',
    0x03E: 'Garayan Sword', 0x03F: 'Mardan Garayan', 0x040: "Ruler's Sword",
    0x041: 'Evilcise', 0x042: 'Small Sword', 0x043: 'Sand Breaker',
    0x044: 'Drain Seeker', 0x045: 'Chopper', 0x046: 'Choora',
    0x047: 'Claymore', 0x048: 'Maneater', 0x049: 'Bone Rapier',
    0x04A: 'Sax', 0x04B: '7 Branch Sword', 0x04C: 'Dusack',
    0x04D: 'Cross Heinder', 0x04E: '7th Heaven', 0x04F: 'Sword of Zeus',
    0x050: 'Chronicle Sword', 0x051: 'Chronicle 2', 0x052: 'Holy Daedalus Blade',
    0x053: 'Muramasa', 0x054: 'Dark Excalibur', 0x055: 'Sargatanas',
    0x056: 'Halloween Blade', 0x057: 'Shining Bravado', 0x058: 'Island King',
    0x059: 'Griffon Fork', 0x05A: 'True Battle Wrench',
    0x05B: 'Magic Brassard', 0x05C: 'Gold Brassard', 0x05D: 'Bandit Brassard',
    0x05E: 'Crystal Brassard', 0x05F: 'Platinum Brassard',
    0x060: 'Goddess Brassard', 0x061: 'Spirit Brassard',
    0x062: 'Destruction Brassard', 0x063: 'Satan Brassard',
    0x064: "Athena's Armlet", 0x065: 'Mobius Bangle', 0x066: 'Angel Shooter',
    0x067: 'Pocklekul', 0x068: 'Thorn Armlet', 0x069: 'Star Armlet',
    0x06A: 'Moon Armlet', 0x06B: 'Sun Armlet', 0x06C: 'Five-Star Armlet',
    0x06D: 'Love', 0x06E: 'Royal Sword',
    0x0AC: 'Monster Notes', 0x0AD: 'Dynamite', 0x0AE: 'Seal-Breaking Scroll',
    0x0AF: 'Flame Crystal', 0x0B0: 'Chill Crystal', 0x0B1: 'Lightning Crystal',
    0x0B2: 'Hunter Crystal', 0x0B3: 'Holy Crystal', 0x0B4: 'Destruction Crystal',
    0x0B5: 'Wind Crystal', 0x0B6: 'Sea Dragon Crystal', 0x0B7: 'Power Crystal',
    0x0B8: 'Protector Crystal',
    0x0BA: 'Garnet', 0x0BB: 'Amethyst', 0x0BC: 'Aquamarine',
    0x0BD: 'Diamond', 0x0BE: 'Emerald', 0x0BF: 'Pearl',
    0x0C0: 'Ruby', 0x0C1: 'Peridot', 0x0C2: 'Sapphire',
    0x0C3: 'Opal', 0x0C4: 'Topaz', 0x0C5: 'Turquoise',
    0x0C6: 'Sun Stone', 0x0C7: 'Moon Stone',
    0x0D2: 'Rolling Log', 0x0D3: 'Sturdy Rock', 0x0D4: 'Rough Rock',
    0x0D5: 'Bundle of Hay', 0x0D6: 'Sturdy Cloth', 0x0D7: 'Gunpowder',
    0x0D8: 'Glass Material', 0x0D9: 'Unknown Bone', 0x0DA: 'Sticky Clay',
    0x0DB: 'Flour', 0x0DC: 'Sugar Cane', 0x0DD: 'Super Hot Pepper',
    0x0DE: 'Poison', 0x0DF: 'Forest Dew', 0x0E0: 'Scrap of Metal',
    0x0E1: 'Gold Bar', 0x0E2: 'Silver Ball', 0x0E3: 'Hunk of Copper',
    0x0E4: 'Light Element', 0x0E5: 'Holy Element', 0x0E6: 'Earth Element',
    0x0E7: 'Water Element', 0x0E8: 'Chill Element', 0x0E9: 'Thunder Element',
    0x0EA: 'Wind Element', 0x0EB: 'Fire Element', 0x0EC: 'Life Element',
    0x0ED: 'Paint (Red)', 0x0EE: 'Paint (Blue)', 0x0EF: 'Paint (Black)',
    0x0F0: 'Paint (Green)', 0x0F1: 'Paint (Orange)', 0x0F2: 'Paint (Yellow)',
    0x0F3: 'Paint (Purple)', 0x0F4: 'Paint (Pink)', 0x0F5: 'Thick Hide',
    0x10C: 'Bread', 0x10D: 'Cheese', 0x10E: 'Premium Chicken',
    0x10F: 'Double Pudding', 0x110: 'Plum Rice Ball',
    0x111: 'Resurrection Powder', 0x112: 'Stamina Drink',
    0x113: 'Antidote Drink', 0x114: 'Holy Water', 0x115: 'Soap',
    0x116: "Medusa's Tear", 0x117: 'Mighty Healing',
    0x118: 'Bomb', 0x119: 'Stone',
    0x125: 'Escape Powder', 0x126: 'Repair Powder', 0x127: 'Level Up Powder',
    0x128: 'Fruit of Eden', 0x129: 'Treasure Chest Key',
    0x12A: 'Gun Repair Powder', 0x160: 'Armband Repair Powder',
    0x16D: 'Earth Gem', 0x16E: 'Water Gem', 0x16F: 'Wind Gem', 0x170: 'Fire Gem',
}

# Georama material buy prices (gilda) — hardcoded from shop script data.
# CShop prices are only in memory when a shop is open; during georama they're gone.
GEORAMA_BUY_PRICES = {
    0x0D0: 20,    # Flour
    0x0D1: 20,    # Sugar Cane
    0x0D2: 20,    # Rolling Log
    0x0D3: 20,    # Rough Rock
    0x0D4: 20,    # Bundle of Hay
    0x0D5: 20,    # Sturdy Rock
    0x0D6: 20,    # Sturdy Cloth
    0x0D7: 20,    # Gunpowder
    0x0D8: 20,    # Glass Material
    0x0D9: 20,    # Unknown Bone
    0x0DA: 20,    # Sticky Clay
    0x0DB: 20,    # Super Hot Pepper
    0x0DC: 20,    # Poison
    0x0DD: 50,    # Hunk of Copper
    0x0DE: 20,    # Forest Dew
    0x0DF: 10,    # Scrap of Metal
    0x0E0: 200,   # Silver Ball
    0x0E1: 1000,  # Gold Bar
    0x0E2: 50,    # Thick Hide
    0x0E4: 60,    # Light Element
    0x0E5: 60,    # Holy Element
    0x0E6: 60,    # Earth Element
    0x0E7: 60,    # Water Element
    0x0E8: 60,    # Chill Element
    0x0E9: 60,    # Thunder Element
    0x0EA: 60,    # Wind Element
    0x0EB: 60,    # Fire Element
    0x0EC: 60,    # Life Element
    0x0ED: 30,    # Paint (Red)
    0x0EE: 30,    # Paint (Blue)
    0x0EF: 30,    # Paint (Black)
    0x0F0: 30,    # Paint (Green)
    0x0F1: 30,    # Paint (Orange)
    0x0F2: 30,    # Paint (Yellow)
    0x0F3: 30,    # Paint (Purple)
    0x0F4: 30,    # Paint (Pink)
}
