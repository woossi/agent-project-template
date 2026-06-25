// reminders.jxa.js — JXA worker for the Apple Reminders <-> Team bridge.
//
// Invoked as:  osascript -l JavaScript reminders.jxa.js '<json-command>'
// The single argv element is a JSON object: { "op": "...", ... }.
// Prints exactly one line of JSON: { ok, op, result } or { ok:false, error }.
//
// JXA is used instead of AppleScript because JSON.stringify handles Korean
// text and Date values cleanly (plain AppleScript `as text` mojibakes UTF-16).
//
// Model mapping (Apple Reminders -> Team):
//   list (목록)      -> Team
//   reminder (할일)  -> Task   { id, name, completed, priority, due, notes }
//   body/notes       -> free-text channel agents annotate progress into

function run(argv) {
  try {
    var cmd = JSON.parse(argv[0]);
    var app = Application("Reminders");
    var op = cmd.op;
    var result;

    if (op === "list-teams") {
      result = listTeams(app);
    } else if (op === "pull") {
      result = pull(app, cmd);
    } else if (op === "add") {
      result = add(app, cmd);
    } else if (op === "complete") {
      result = setCompleted(app, cmd, true);
    } else if (op === "reopen") {
      result = setCompleted(app, cmd, false);
    } else if (op === "annotate") {
      result = annotate(app, cmd);
    } else if (op === "create-list") {
      result = createList(app, cmd);
    } else if (op === "delete-list") {
      result = deleteList(app, cmd);
    } else {
      return JSON.stringify({ ok: false, error: "unknown op: " + String(op) });
    }
    return JSON.stringify({ ok: true, op: op, result: result });
  } catch (e) {
    return JSON.stringify({ ok: false, error: String(e) });
  }
}

function findList(app, name) {
  var lists = app.lists();
  for (var i = 0; i < lists.length; i++) {
    if (lists[i].name() === name) return lists[i];
  }
  throw new Error("list (team) not found: " + name);
}

function reminderToObj(r) {
  var due = null;
  try { var d = r.dueDate(); if (d) due = d.toISOString(); } catch (e) {}
  var notes = null;
  try { var b = r.body(); if (b) notes = b; } catch (e) {}
  return {
    id: r.id(),
    name: r.name(),
    completed: r.completed(),
    priority: r.priority(),
    due: due,
    notes: notes
  };
}

function findReminder(app, listName, cmd) {
  var l = findList(app, listName);
  var rems = l.reminders();
  for (var i = 0; i < rems.length; i++) {
    if (cmd.id && rems[i].id() === cmd.id) return rems[i];
    if (!cmd.id && cmd.name && rems[i].name() === cmd.name) return rems[i];
  }
  throw new Error("task not found in team '" + listName + "': " + (cmd.id || cmd.name));
}

function listTeams(app) {
  var lists = app.lists();
  var out = [];
  for (var i = 0; i < lists.length; i++) {
    var rems = lists[i].reminders();
    var open = 0;
    for (var j = 0; j < rems.length; j++) { if (!rems[j].completed()) open++; }
    out.push({ team: lists[i].name(), id: lists[i].id(), total: rems.length, open: open });
  }
  return out;
}

function pull(app, cmd) {
  var l = findList(app, cmd.list);
  var rems = l.reminders();
  var out = [];
  for (var i = 0; i < rems.length; i++) {
    var obj = reminderToObj(rems[i]);
    if (cmd.includeCompleted || !obj.completed) out.push(obj);
  }
  return out;
}

function add(app, cmd) {
  var l = findList(app, cmd.list);
  var props = { name: cmd.name };
  if (cmd.notes != null) props.body = cmd.notes;
  if (cmd.priority != null) props.priority = cmd.priority;
  if (cmd.due != null) props.dueDate = new Date(cmd.due);
  var r = app.Reminder(props);
  l.reminders.push(r);
  return reminderToObj(r);
}

function setCompleted(app, cmd, value) {
  var r = findReminder(app, cmd.list, cmd);
  r.completed = value;
  return reminderToObj(r);
}

function annotate(app, cmd) {
  var r = findReminder(app, cmd.list, cmd);
  var existing = "";
  try { existing = r.body() || ""; } catch (e) {}
  r.body = existing ? (existing + "\n" + cmd.note) : cmd.note;
  return reminderToObj(r);
}

function createList(app, cmd) {
  var nl = app.List({ name: cmd.list });
  app.lists.push(nl);
  return { team: cmd.list, created: true };
}

function deleteList(app, cmd) {
  var l = findList(app, cmd.list);
  app.delete(l);
  return { team: cmd.list, deleted: true };
}
