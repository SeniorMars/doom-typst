#import "../lib.typ": play, new-game, advance, info, framebuffer, save-game, saved-bytes, load-game
#{
  let wad = read("../assets/freedoom1.wad", encoding: none)
  let base = new-game(wad, tics: 1)
  let original = info(base)
  assert.eq((original.health, original.ammo, original.map, original.episode, original.state), (100, 50, 1, 1, 0))
  let trace = "wwwwjjffffxxxxwwll" * 4
  let once = advance(base, trace)
  let split = advance(advance(base, trace.slice(0, 17)), trace.slice(17))
  assert.eq(info(once), info(split))
  assert.eq(framebuffer(once), framebuffer(split))
  assert.eq(info(play(trace, tics: 1)), info(once))
  assert.eq(info(base), original)
  assert(framebuffer(once) != framebuffer(base))
  assert.eq(info(once).tic, original.tic + trace.len())
  assert(info(once).ammo < original.ammo)
  assert.eq(info(advance(base, "m")).automap, true)
  assert.eq(info(advance(base, "p")).menu, true)
  let data = saved-bytes(save-game(once))
  let loaded = load-game(base, data)
  for key in ("x", "y", "angle", "health", "armor", "ammo", "kills", "items", "secrets", "episode", "map", "weapon") {
    assert.eq(info(loaded).at(key), info(once).at(key))
  }
  // Smoke-test every included level, without claiming a full campaign run.
  for episode in range(1, 5) {
    for map in range(1, 10) {
      let game = new-game(wad, episode: episode, map: map, tics: 1)
      assert.eq((info(game).episode, info(game).map, info(game).state), (episode, map, 0))
      assert.eq(framebuffer(game).len(), 320 * 200 * 3)
      let moved = advance(game, "wwjjffxe")
      assert.eq(info(moved).tic, info(game).tic + 8)
      assert.eq(framebuffer(moved).len(), 320 * 200 * 3)
    }
  }
  [Freedoom gameplay, saves, and all 36 level starts passed.]
}
