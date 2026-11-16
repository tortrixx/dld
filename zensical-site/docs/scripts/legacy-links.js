// Preserve known Docsify inbound links; leave all native anchors unchanged.
(() => {
  const route = location.hash.slice(2).split("?")[0].replace(/\.md$/, "");
  if (!location.hash.startsWith("#/") || !location.pathname.endsWith("/dld/")) return;
  const modules = ["01_system_top", "02_clock_keypad", "03_game_fsm",
    "04_puzzle_engine", "05_rom_random", "06_display_audio"];
  const pages = Object.fromEntries(modules.map(name => ["subsystems/" + name, "modules/" + name + "/"]));
  pages[""] = "";
  pages["README"] = "";
  if (Object.hasOwn(pages, route)) location.replace(new URL(pages[route], location.href.split("#")[0]));
})();
