// Compare rendering effects against an explicitly supplied reference build.
#{
  let reference = plugin(sys.inputs.at("reference"))
  let candidate = plugin(sys.inputs.at("candidate"))
  let wad = read("../assets/freedoom1.wad", encoding: none)
  let config = bytes((3, 1, 1, 4))
  let original = plugin.transition(reference.init, wad, config)
  let saved = plugin.transition(original.save, bytes((0,))).saved(bytes((0,)))
  // Vanilla save layout from p_saveg.c: 50-byte header padded to 52,
  // player pointer/state/ticcmd (16), seven 32-bit fields (28), then powers.
  // Set timed powerups through a valid engine-generated save, not test exports.
  for offset in (96, 104) {
    assert.eq(saved.slice(offset, offset + 4), bytes((0, 0, 0, 0)))
    let powered = saved.slice(0, offset) + bytes((232, 3, 0, 0)) + saved.slice(offset + 4)
    let old = plugin.transition(original.load, powered)
    let new = plugin.transition(plugin.transition(candidate.init, wad, config).load, powered)
    assert.eq(new.frame(), old.frame())
    for input in ("x", "xx", "www", "llff", "p", "p", "m", "m", "jjff", "xxxx") {
      old = plugin.transition(old.advance, bytes(input))
      new = plugin.transition(new.advance, bytes(input))
      assert.eq(new.info(), old.info())
      assert.eq(new.frame(), old.frame(), message: "Powerup rendering differs after " + input)
    }
  }
  [Invulnerability and invisibility frame comparisons passed.]
}
