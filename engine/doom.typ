// Repository compatibility entry point, with the existing shareware IWAD.
#import "core.typ": new-game, advance, info, framebuffer, save-game, saved-bytes, load-game
#import "core.typ" as core
#let play = core.play.with(wad: read("../assets/doom1.wad", encoding: none))
#let save-path = sys.inputs.at("save", default: none)
#let doom = core.doom.with(
  wad: read("../assets/doom1.wad", encoding: none),
  save: if save-path == none { none } else {
    bytes(json(if save-path.starts-with("/") { save-path } else { "/" + save-path }))
  },
)
