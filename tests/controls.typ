#import "../lib.typ": default-actions, parse-actions, play, info, framebuffer, save-game, saved-bytes
#{
  let wad = read("../assets/freedoom1.wad", encoding: none)
  let canonical = "wasdjlfexm1234567qzWASDpikhocbynr"
  assert.eq(parse-actions(canonical), canonical)
  assert.eq(parse-actions("R"), "r")
  assert.eq(parse-actions("  \n\t!?"), "")
  assert.eq(parse-actions([ww // ff ignored
    jj
  ]), "wwjj")
  assert.eq(parse-actions("fvv eu ↑W", actions: (fire: ("v",), use: ("u",), forward: ("w", "↑"))), "ffewW")
  assert.eq(parse-actions("ffxx", actions: (fire: ())), "xx")
  assert.eq(parse-actions("rRv", actions: (restart: ("v",))), "r")
  assert.eq(parse-actions("rV", actions: (restart: (), fire: ("r", "V"))), "ff")
  assert.eq(parse-actions(raw("#*"), actions: (fire: ("#", "*"))), "ff")
  assert.eq(default-actions.fire, ("f",))
  // Unicode keys normalize before byte-based replay chunking.
  let custom = (forward: ("↑",), turn-left: ("←",), fire: ("v",), restart: ("t",))
  let input = "↑↑←←vvxx" * 3
  let reference = play("wwjjffxx" * 3, wad: wad, tics: 1)
  for size in (4, 8, 16) {
    let actual = play(input, wad: wad, actions: custom, tics: 1, chunk-size: size)
    assert.eq(info(actual), info(reference))
    assert.eq(framebuffer(actual), framebuffer(reference))
  }
  let reset = play("↑↑t", wad: wad, actions: custom, tics: 1)
  assert.eq(info(reset), info(play("", wad: wad, tics: 1)))
  let saved = saved-bytes(save-game(reference))
  let restarted = play("↑↑t", wad: wad, actions: custom, save: saved, tics: 1)
  assert.eq(info(restarted), info(reset))
  let resumed = play("↑", wad: wad, actions: custom, save: saved, tics: 1)
  assert.eq(info(resumed), info(play("w", wad: wad, save: saved, tics: 1)))
  [Keybinding and replay checks passed.]
}
