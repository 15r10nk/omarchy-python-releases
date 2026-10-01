.pragma library

// A starred series follows its next stable release, including patches.
// The "all" mode also includes prereleases. No dates means no countdown.
function nextRelease(report, favorite, mode) {
  if (!favorite) return report.next || null
  var branch = (report.branches || []).find(function(b) { return b.version === favorite })
  if (!branch) return null
  var events = branch.events.slice()
  var first = branch.version + ".0"
  if (/^\d{4}-\d{2}-\d{2}$/.test(branch.first) && !events.some(function(e) { return e.version === first }))
    events.push({version: first, date: branch.first, kind: "stable", confirmed: false, url: branch.url})
  events = events.filter(function(e) {
    return e.date >= report.today && !e.confirmed && e.kind !== "development"
      && (mode === "all" || e.kind === "stable")
  }).sort(function(a, b) { return a.date.localeCompare(b.date) || a.version.localeCompare(b.version) })
  if (!events.length) return null
  var result = Object.assign({}, events[0])
  result.days = Math.round((Date.parse(result.date + "T00:00:00Z") - Date.parse(report.today + "T00:00:00Z")) / 86400000)
  return result
}
