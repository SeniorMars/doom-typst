#import "../engine/doom.typ": new-game, advance, info, framebuffer, save-game, saved-bytes, load-game
#{
  let wad = read("../assets/doom1.wad", encoding: none)
  let base = new-game(wad, tics: 1)
  let moved = advance(base, "wwwwwwwwxxxxfffxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
  let before = info(moved)
  let saved = save-game(moved)
  let data = saved-bytes(saved)
  assert(data.len() > 1000)
  assert.eq(data.at(data.len() - 1), 0x1d)
  assert.eq(info(saved), before, message: "Saving must not advance time or mutate the player")
  assert.eq(info(moved), before)
  let elsewhere = advance(saved, "llllwwwwwwww")
  assert(info(elsewhere).angle != before.angle)
  let restored = load-game(elsewhere, data)
  let after = info(restored)
  for key in ("x", "y", "angle", "health", "armor", "ammo", "kills", "items", "secrets", "episode", "map", "weapon", "ceiling_sum") {
    assert.eq(after.at(key), before.at(key), message: "Native save must restore " + key)
  }
  assert.eq(info(advance(restored, "x")).tic, after.tic + 1)
  let fresh = load-game(new-game(wad, map: 2), data)
  assert.eq(info(fresh).map, 1)
  assert.eq(info(fresh).x, before.x)
  // Save slot replacement and separate slots use the original temp/rename path.
  let slot1 = save-game(elsewhere, slot: 1)
  assert.eq(saved-bytes(slot1), data)
  assert(saved-bytes(slot1, slot: 1) != data)
  let replaced = save-game(elsewhere)
  assert(saved-bytes(replaced) != data)
  // Original save menu: choose Save Game, first slot, type W, confirm.
  let menu-saved = advance(base, "pkkkccwcxx")
  assert(not info(menu-saved).menu)
  assert(saved-bytes(menu-saved).len() > 1000)
  let menu-moved = advance(menu-saved, "wwwwwwww")
  // Main menu remembers Save Game; move up once to Load Game, choose first slot.
  let menu-loaded = advance(menu-moved, "picc")
  assert.eq(info(menu-loaded).x, info(base).x)
  assert.eq(info(menu-loaded).y, info(base).y)
  // Quit is local to the derived snapshot, and does not trap the compiler.
  let quit = advance(base, "pkkkkkcy")
  assert(info(quit).quit)
  assert.eq(info(advance(quit, "wwwfff")), info(quit))
  assert(not info(base).quit)
  assert(not info(load-game(quit, data)).quit)
  [Native save/load and quit checks passed.]
}
