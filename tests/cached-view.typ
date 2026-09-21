#import "../engine/core.typ": new-game, play, view, info, framebuffer, save-game, saved-bytes
#{
  let wad = read("../assets/freedoom1.wad", encoding: none)
  let base = new-game(wad, tics: 1)
  let original = (state: info(base), frame: framebuffer(base))
  let check(input, ..options) = {
    let cached = view(input, wad: wad, tics: 1, ..options)
    let normal = play(input, wad: wad, tics: 1, ..options)
    assert.eq(cached.state, info(normal))
    assert.eq(cached.frame, framebuffer(normal))
  }
  for input in ("", "wwjjff", "ww", "p", "pk", "pkc", "", "mm", "wwrjj", "w"*65, "w"*31) {
    check(input)
  }
  // Cached calls cannot contaminate public transition-based game handles.
  assert.eq(info(base), original.state)
  assert.eq(framebuffer(base), original.frame)
  let saved = saved-bytes(save-game(play("wwwjjff", wad: wad, tics: 1)))
  for input in ("", "ww", "wwj", "w", "wwr", "wwrjj") {
    check(input, save: saved)
  }
  check("uuvv", actions: (forward: ("u",), turn-left: ("v",)))
  // Beyond the old per-call limit; cache output must match chunked simulation.
  check("wwjjffex"*513)
  [Cached metadata, pixels, isolation, save import, restart, bindings, and long history passed.]
}
