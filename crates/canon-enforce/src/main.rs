use serde_json::Value;
use std::collections::{BTreeMap, BTreeSet};
use std::env;
use std::fs;
use std::io::{self, Read};
use std::path::{Path, PathBuf};

#[derive(Clone, Copy)]
struct KindSpec {
    kind: &'static str,
    dir: &'static str,
    id: &'static str,
    prefix: &'static str,
    links: &'static [(&'static str, &'static str)],
}

const CANON: &[KindSpec] = &[
    KindSpec {
        kind: "claim",
        dir: ".project/claims",
        id: "claim_id",
        prefix: "C",
        links: &[
            ("evidence", "evidence"),
            ("counter_evidence", "evidence"),
            ("grounds", "lit_prop"),
            ("counter_grounds", "lit_prop"),
            ("risks", "risk"),
        ],
    },
    KindSpec {
        kind: "evidence",
        dir: ".project/evidence",
        id: "evidence_id",
        prefix: "E",
        links: &[("provenance", "provenance"), ("derived_from", "evidence")],
    },
    KindSpec {
        kind: "provenance",
        dir: ".project/provenance",
        id: "artifact_id",
        prefix: "P",
        links: &[("related_claims", "claim"), ("risks", "risk")],
    },
    KindSpec {
        kind: "lit_prop",
        dir: ".project/lit_props",
        id: "lit_prop_id",
        prefix: "LP",
        links: &[],
    },
    KindSpec {
        kind: "data_registry",
        dir: ".project/data_registry",
        id: "data_id",
        prefix: "D",
        links: &[],
    },
    KindSpec {
        kind: "runs",
        dir: ".project/runs",
        id: "run_id",
        prefix: "RUN",
        links: &[],
    },
    KindSpec {
        kind: "risk",
        dir: ".project/risks",
        id: "risk_id",
        prefix: "R",
        links: &[("related_claims", "claim")],
    },
];

const RELATION_TYPES: &[&str] = &[
    "depends_on",
    "contrasts_with",
    "limits",
    "contradicts",
    "elaborates",
    "supported_by_lit",
];

const DEPRECATED: &[&str] = &["deprecated", "replaced"];

#[derive(Clone)]
struct Record {
    value: Value,
}

type Graph = BTreeMap<&'static str, BTreeMap<String, Record>>;

#[derive(Default)]
struct Validation {
    errors: Vec<String>,
    warnings: Vec<String>,
}

fn json_str<'a>(value: &'a Value, key: &str) -> Option<&'a str> {
    value
        .get(key)
        .and_then(Value::as_str)
        .map(str::trim)
        .filter(|s| !s.is_empty())
}

fn status_is_deprecated(value: &Value) -> bool {
    json_str(value, "status")
        .map(|s| DEPRECATED.contains(&s.to_ascii_lowercase().as_str()))
        .unwrap_or(false)
}

fn read_json(path: &Path) -> Option<Value> {
    let text = fs::read_to_string(path).ok()?;
    serde_json::from_str(&text).ok()
}

fn load_kind(root: &Path, spec: &'static KindSpec) -> BTreeMap<String, Record> {
    let mut out = BTreeMap::new();
    let dir = root.join(spec.dir);
    let Ok(entries) = fs::read_dir(dir) else {
        return out;
    };
    let mut paths: Vec<PathBuf> = entries
        .filter_map(Result::ok)
        .map(|entry| entry.path())
        .filter(|path| path.extension().and_then(|s| s.to_str()) == Some("json"))
        .collect();
    paths.sort();
    for path in paths {
        let Some(value) = read_json(&path) else {
            continue;
        };
        let Some(rid) = json_str(&value, spec.id) else {
            continue;
        };
        out.entry(rid.to_string())
            .or_insert_with(|| Record { value });
    }
    out
}

fn load_all(root: &Path) -> Graph {
    let mut graph = BTreeMap::new();
    for spec in CANON {
        graph.insert(spec.kind, load_kind(root, spec));
    }
    graph
}

fn file_ids(root: &Path, spec: &'static KindSpec) -> Vec<(String, String)> {
    let dir = root.join(spec.dir);
    let Ok(entries) = fs::read_dir(dir) else {
        return Vec::new();
    };
    let mut paths: Vec<PathBuf> = entries
        .filter_map(Result::ok)
        .map(|entry| entry.path())
        .filter(|path| path.extension().and_then(|s| s.to_str()) == Some("json"))
        .collect();
    paths.sort();
    let mut pairs = Vec::new();
    for path in paths {
        let Some(value) = read_json(&path) else {
            continue;
        };
        if let Some(rid) = json_str(&value, spec.id) {
            pairs.push((
                rid.to_string(),
                path.file_name()
                    .and_then(|s| s.to_str())
                    .unwrap_or("")
                    .to_string(),
            ));
        }
    }
    pairs
}

fn schema_required(root: &Path, kind: &str) -> Vec<String> {
    let path = root
        .join(".project/schema")
        .join(format!("{kind}.schema.json"));
    if let Some(value) = read_json(&path) {
        if let Some(list) = value.get("required").and_then(Value::as_array) {
            return list
                .iter()
                .filter_map(Value::as_str)
                .map(ToOwned::to_owned)
                .collect();
        }
    }
    if kind == "evidence" {
        return [
            "evidence_id",
            "value",
            "label",
            "provenance",
            "status",
            "by",
            "ts_ns",
        ]
        .iter()
        .map(|s| s.to_string())
        .collect();
    }
    Vec::new()
}

fn validate_record_shape(
    root: &Path,
    spec: &'static KindSpec,
    rid: &str,
    rec: &Value,
) -> Vec<String> {
    let mut errors = Vec::new();
    if !json_str(rec, spec.id)
        .map(|id| id.starts_with(spec.prefix))
        .unwrap_or(false)
    {
        errors.push(format!(
            "{} schema: record '{}' field '{}' must start with '{}'",
            spec.kind, rid, spec.id, spec.prefix
        ));
    }
    for field in schema_required(root, spec.kind) {
        let missing = match rec.get(&field) {
            None | Some(Value::Null) => true,
            Some(Value::String(s)) => s.is_empty(),
            _ => false,
        };
        if missing {
            errors.push(format!(
                "{} schema: record '{}' missing required field '{}'",
                spec.kind, rid, field
            ));
        }
    }
    errors
}

fn validate(root: &Path) -> Validation {
    let graph = load_all(root);
    let mut v = Validation::default();

    for spec in CANON {
        let mut seen: BTreeMap<String, String> = BTreeMap::new();
        for (rid, file) in file_ids(root, spec) {
            if let Some(first) = seen.get(&rid) {
                v.errors.push(format!(
                    "id clash: {} '{}' in both {} and {}",
                    spec.kind, rid, first, file
                ));
            } else {
                seen.insert(rid, file);
            }
        }
    }

    for spec in CANON {
        if let Some(kind_graph) = graph.get(spec.kind) {
            for (rid, rec) in kind_graph {
                v.errors
                    .extend(validate_record_shape(root, spec, rid, &rec.value));
            }
        }
    }

    let mut referenced: BTreeMap<&'static str, BTreeSet<String>> = BTreeMap::new();
    for spec in CANON {
        referenced.insert(spec.kind, BTreeSet::new());
    }

    for spec in CANON {
        let Some(kind_graph) = graph.get(spec.kind) else {
            continue;
        };
        for (rid, rec) in kind_graph {
            let active = !status_is_deprecated(&rec.value);
            for (field, target_kind) in spec.links {
                let targets = rec.value.get(*field).unwrap_or(&Value::Null);
                if targets.is_null() {
                    continue;
                }
                let Some(arr) = targets.as_array() else {
                    v.errors.push(format!(
                        "{} '{}': field '{}' must be a list",
                        spec.kind, rid, field
                    ));
                    continue;
                };
                for target in arr {
                    let Some(tid) = target.as_str().map(str::trim).filter(|s| !s.is_empty()) else {
                        continue;
                    };
                    referenced
                        .entry(target_kind)
                        .or_default()
                        .insert(tid.to_string());
                    let target = graph.get(target_kind).and_then(|g| g.get(tid));
                    match target {
                        None => v.errors.push(format!(
                            "dangling link: {} '{}'.{} -> {} '{}' (not found)",
                            spec.kind, rid, field, target_kind, tid
                        )),
                        Some(tgt) if active && status_is_deprecated(&tgt.value) => {
                            v.errors.push(format!(
                                "deprecated ref: active {} '{}'.{} -> {} '{}' (status={})",
                                spec.kind,
                                rid,
                                field,
                                target_kind,
                                tid,
                                json_str(&tgt.value, "status").unwrap_or("?")
                            ));
                        }
                        _ => {}
                    }
                }
            }
        }
    }

    for kind in ["evidence", "provenance"] {
        if let Some(kind_graph) = graph.get(kind) {
            for (rid, rec) in kind_graph {
                if status_is_deprecated(&rec.value) {
                    continue;
                }
                if !referenced
                    .get(kind)
                    .map(|s| s.contains(rid))
                    .unwrap_or(false)
                {
                    v.warnings.push(format!(
                        "orphan {} '{}': not referenced by any record",
                        kind, rid
                    ));
                }
            }
        }
    }

    for spec in CANON {
        let Some(kind_graph) = graph.get(spec.kind) else {
            continue;
        };
        for (rid, rec) in kind_graph {
            let Some(sup) = rec.value.get("supersedes") else {
                continue;
            };
            let mut sup_ids = Vec::new();
            if let Some(s) = sup.as_str() {
                if !s.trim().is_empty() {
                    sup_ids.push(s.trim().to_string());
                }
            } else if let Some(arr) = sup.as_array() {
                for item in arr {
                    if let Some(s) = item.as_str().map(str::trim).filter(|s| !s.is_empty()) {
                        sup_ids.push(s.to_string());
                    }
                }
            }
            for sid in sup_ids {
                if sid == *rid {
                    v.errors.push(format!(
                        "self-supersedes: {} '{}'.supersedes -> itself",
                        spec.kind, rid
                    ));
                    continue;
                }
                let target = graph.get(spec.kind).and_then(|g| g.get(&sid));
                match target {
                    None => v.errors.push(format!(
                        "dangling supersedes: {} '{}'.supersedes -> {} '{}' (not found)",
                        spec.kind, rid, spec.kind, sid
                    )),
                    Some(tgt) if !status_is_deprecated(&tgt.value) => v.warnings.push(format!(
                        "un-retired predecessor: {} '{}' supersedes still-active '{}' (status={}) - retire it (deprecated/replaced)",
                        spec.kind,
                        rid,
                        sid,
                        json_str(&tgt.value, "status").unwrap_or("?")
                    )),
                    _ => {}
                }
            }
        }
    }

    validate_scalar_links(&graph, &mut v);
    validate_relations(&graph, &mut v);
    validate_bibkeys(root, &graph, &mut v);
    clarity_audit(&graph, &mut v);
    v
}

fn validate_scalar_links(graph: &Graph, v: &mut Validation) {
    let runs = graph.get("runs").cloned().unwrap_or_default();
    let data = graph.get("data_registry").cloned().unwrap_or_default();
    let Some(prov) = graph.get("provenance") else {
        return;
    };
    for (rid, rec) in prov {
        if let Some(run) = json_str(&rec.value, "run_id") {
            if run != "RUN-UNSPECIFIED" && !runs.contains_key(run) {
                v.warnings.push(format!(
                    "unwired run_id: provenance '{}'.run_id -> runs '{}' (not found; placeholder until S6)",
                    rid, run
                ));
            }
        }
        if let Some(src) = json_str(&rec.value, "source_data") {
            if src != "D-UNSPECIFIED" && !data.contains_key(src) {
                v.warnings.push(format!(
                    "unwired source_data: provenance '{}'.source_data -> data_registry '{}' (not found; placeholder until S6)",
                    rid, src
                ));
            }
        }
    }
}

fn validate_relations(graph: &Graph, v: &mut Validation) {
    let Some(claims) = graph.get("claim") else {
        return;
    };
    let lit_props = graph.get("lit_prop").cloned().unwrap_or_default();
    let mut deps: BTreeMap<String, BTreeSet<String>> = BTreeMap::new();
    for (rid, rec) in claims {
        let Some(rels) = rec.value.get("relations") else {
            continue;
        };
        let Some(arr) = rels.as_array() else {
            v.errors
                .push(format!("claim '{}': relations must be a list", rid));
            continue;
        };
        for rel in arr {
            let Some(obj) = rel.as_object() else {
                v.errors
                    .push(format!("claim '{}': each relation must be an object", rid));
                continue;
            };
            let rtype = obj.get("type").and_then(Value::as_str).unwrap_or("");
            let target = obj
                .get("target")
                .and_then(Value::as_str)
                .unwrap_or("")
                .trim();
            if !RELATION_TYPES.contains(&rtype) {
                v.errors.push(format!(
                    "claim '{}': unknown relation type '{}'",
                    rid, rtype
                ));
            }
            if target.is_empty() {
                v.errors.push(format!(
                    "claim '{}': relation '{}' has no target",
                    rid, rtype
                ));
                continue;
            }
            let target_exists = if rtype == "supported_by_lit" {
                lit_props.contains_key(target)
            } else {
                claims.contains_key(target)
            };
            if !target_exists {
                let target_kind = if rtype == "supported_by_lit" {
                    "lit_prop"
                } else {
                    "claim"
                };
                v.errors.push(format!(
                    "dangling relation: claim '{}' {} -> {} '{}' (not found)",
                    rid, rtype, target_kind, target
                ));
            }
            if rtype == "depends_on" && claims.contains_key(target) {
                deps.entry(rid.clone())
                    .or_default()
                    .insert(target.to_string());
            }
        }
    }

    let mut color: BTreeMap<String, u8> = claims.keys().map(|k| (k.clone(), 0)).collect();
    for claim in claims.keys() {
        if color.get(claim) == Some(&0) {
            dfs_relation(claim, &deps, &mut color, &mut Vec::new(), &mut v.errors);
        }
    }
}

fn dfs_relation(
    node: &str,
    deps: &BTreeMap<String, BTreeSet<String>>,
    color: &mut BTreeMap<String, u8>,
    stack: &mut Vec<String>,
    errors: &mut Vec<String>,
) {
    color.insert(node.to_string(), 1);
    stack.push(node.to_string());
    if let Some(nexts) = deps.get(node) {
        for next in nexts {
            match color.get(next).copied().unwrap_or(2) {
                1 => {
                    let mut cycle = stack.clone();
                    cycle.push(next.clone());
                    errors.push(format!(
                        "relation cycle (depends_on): {}",
                        cycle.join(" -> ")
                    ));
                }
                0 => dfs_relation(next, deps, color, stack, errors),
                _ => {}
            }
        }
    }
    stack.pop();
    color.insert(node.to_string(), 2);
}

fn read_bibkeys(root: &Path) -> Option<BTreeSet<String>> {
    let mut candidates = Vec::new();
    if let Some(parent) = root.parent() {
        candidates.push(parent.join("research/UMC/refs.bib"));
    }
    candidates.push(root.join("refs.bib"));
    for path in candidates {
        let Ok(text) = fs::read_to_string(path) else {
            continue;
        };
        let mut keys = BTreeSet::new();
        for line in text.lines().map(str::trim) {
            if line.starts_with('@') && line.contains('{') {
                let key = line
                    .split_once('{')
                    .map(|(_, rest)| rest.trim_end_matches(',').trim().to_string());
                if let Some(key) = key {
                    if !key.is_empty() {
                        keys.insert(key);
                    }
                }
            }
        }
        return Some(keys);
    }
    None
}

fn validate_bibkeys(root: &Path, graph: &Graph, v: &mut Validation) {
    let Some(lit) = graph.get("lit_prop") else {
        return;
    };
    if lit.is_empty() {
        return;
    }
    let keys = read_bibkeys(root);
    for (rid, rec) in lit {
        let Some(key) = json_str(&rec.value, "bibkey") else {
            v.errors.push(format!(
                "lit_prop '{}': missing bibkey (refs.bib SSOT link)",
                rid
            ));
            continue;
        };
        match &keys {
            None => v.warnings.push(format!(
                "lit_prop '{}'.bibkey '{}': refs.bib not readable here - bibkey unverified (outside read scope?)",
                rid, key
            )),
            Some(keys) if !keys.contains(key) => v.errors.push(format!(
                "dangling bibkey: lit_prop '{}'.bibkey -> '{}' (not in refs.bib)",
                rid, key
            )),
            _ => {}
        }
    }
}

fn clarity_audit(graph: &Graph, v: &mut Validation) {
    let probes = [("claim", "claim"), ("lit_prop", "proposition")];
    let lexicon = [
        (
            "R8",
            ["기능한다", "작용한다", "위치한다", "구성된다"].as_slice(),
        ),
        (
            "R9",
            [
                "영향을 미쳤다",
                "영향을 미친다",
                "효과가 있었다",
                "초래했다",
                "야기했다",
            ]
            .as_slice(),
        ),
        (
            "R10",
            ["작지만", "보조적으로", "제한적으로", "맥락적으로"].as_slice(),
        ),
    ];
    for (kind, field) in probes {
        let Some(records) = graph.get(kind) else {
            continue;
        };
        for (rid, rec) in records {
            let Some(text) = json_str(&rec.value, field) else {
                continue;
            };
            for (rule, terms) in lexicon {
                let hits: Vec<&str> = terms
                    .iter()
                    .copied()
                    .filter(|term| text.contains(term))
                    .collect();
                if !hits.is_empty() {
                    v.warnings.push(format!(
                        "clarity {}: {} '{}' uses {:?} - review (R8 weak-verb / R9 overclaimed-causation / R10 hedge-stacking)",
                        rule, kind, rid, hits
                    ));
                }
            }
        }
    }
}

fn backrefs(graph: &Graph) -> BTreeMap<&'static str, BTreeMap<String, Vec<String>>> {
    let mut back: BTreeMap<&'static str, BTreeMap<String, BTreeSet<String>>> = BTreeMap::new();
    for spec in CANON {
        back.insert(spec.kind, BTreeMap::new());
    }
    for spec in CANON {
        let Some(records) = graph.get(spec.kind) else {
            continue;
        };
        for (rid, rec) in records {
            for (field, target_kind) in spec.links {
                let Some(arr) = rec.value.get(*field).and_then(Value::as_array) else {
                    continue;
                };
                for target in arr {
                    let Some(tid) = target.as_str().map(str::trim).filter(|s| !s.is_empty()) else {
                        continue;
                    };
                    back.entry(target_kind)
                        .or_default()
                        .entry(tid.to_string())
                        .or_default()
                        .insert(rid.clone());
                }
            }
        }
    }
    back.into_iter()
        .map(|(kind, ids)| {
            let ids = ids
                .into_iter()
                .map(|(id, refs)| (id, refs.into_iter().collect()))
                .collect();
            (kind, ids)
        })
        .collect()
}

fn fold_claim_sentence(rec: &Value) -> String {
    let Some(comp) = rec.get("components").and_then(Value::as_object) else {
        return String::new();
    };
    let slots = [
        ("scope", ["condition", "analysis_basis"].as_slice()),
        ("target", ["text"].as_slice()),
        ("comparison", ["baseline", "criterion"].as_slice()),
        ("finding", ["text"].as_slice()),
    ];
    let mut parts = Vec::new();
    for (slot, keys) in slots {
        let Some(obj) = comp.get(slot).and_then(Value::as_object) else {
            continue;
        };
        for key in keys {
            if let Some(text) = obj.get(*key).and_then(Value::as_str).map(str::trim) {
                if !text.is_empty() {
                    parts.push(text.to_string());
                    break;
                }
            }
        }
    }
    parts.join(" ")
}

fn fold_one(root: &Path, spec: &'static KindSpec, refs: &BTreeMap<String, Vec<String>>) -> String {
    let graph = load_kind(root, spec);
    let mut lines = vec![
        format!("# {} index (derived view - do not hand-edit)", spec.kind),
        String::new(),
        format!(
            "Regenerated from `{}/*.json` by `canon-enforce fold`. The immutable JSON records are the canon. Back-references (cited_by) are computed, not stored.",
            spec.dir
        ),
        String::new(),
    ];
    if graph.is_empty() {
        lines.push("_(no records)_".to_string());
        return lines.join("\n") + "\n";
    }
    for (rid, rec) in graph {
        let status = json_str(&rec.value, "status").unwrap_or("?");
        let cited_by = refs.get(&rid).cloned().unwrap_or_default();
        let (head, links, extra) = match spec.kind {
            "claim" => {
                let folded = fold_claim_sentence(&rec.value);
                let head = if folded.is_empty() {
                    json_str(&rec.value, "claim").unwrap_or("").to_string()
                } else {
                    folded
                };
                let links = format!(
                    "evidence={} grounds={} relations={}",
                    display_json_field(&rec.value, "evidence"),
                    display_json_field(&rec.value, "grounds"),
                    display_relations(&rec.value)
                );
                let extra = format!(
                    "used_in={} verified_by={}",
                    display_json_field(&rec.value, "used_in"),
                    json_str(&rec.value, "verified_by").unwrap_or("?")
                );
                (head, links, extra)
            }
            "evidence" => (
                format!(
                    "{} - {}",
                    json_str(&rec.value, "value").unwrap_or("?"),
                    json_str(&rec.value, "label").unwrap_or("")
                ),
                format!(
                    "provenance={}",
                    display_json_field(&rec.value, "provenance")
                ),
                format!(
                    "checked_by={}",
                    json_str(&rec.value, "checked_by").unwrap_or("?")
                ),
            ),
            "provenance" => (
                format!(
                    "{}: {}",
                    json_str(&rec.value, "artifact_type").unwrap_or("?"),
                    json_str(&rec.value, "value").unwrap_or("")
                ),
                format!(
                    "related_claims={} source_data={} run_id={}",
                    display_json_field(&rec.value, "related_claims"),
                    json_str(&rec.value, "source_data").unwrap_or("?"),
                    json_str(&rec.value, "run_id").unwrap_or("?")
                ),
                format!(
                    "loc={}",
                    json_str(&rec.value, "manuscript_location").unwrap_or("?")
                ),
            ),
            "lit_prop" => (
                format!(
                    "{}: {}",
                    json_str(&rec.value, "role").unwrap_or("?"),
                    json_str(&rec.value, "proposition").unwrap_or("")
                ),
                format!(
                    "bibkey={} -> refs.bib",
                    json_str(&rec.value, "bibkey").unwrap_or("?")
                ),
                format!(
                    "loc={} argument_step={}",
                    json_str(&rec.value, "manuscript_location").unwrap_or("?"),
                    json_str(&rec.value, "argument_step").unwrap_or("?")
                ),
            ),
            "data_registry" => (
                json_str(&rec.value, "label").unwrap_or("").to_string(),
                format!(
                    "manifest_ref={}",
                    json_str(&rec.value, "manifest_ref").unwrap_or("?")
                ),
                format!(
                    "period={} area={}",
                    json_str(&rec.value, "period").unwrap_or("?"),
                    json_str(&rec.value, "area").unwrap_or("?")
                ),
            ),
            "runs" => (
                json_str(&rec.value, "label").unwrap_or("").to_string(),
                format!(
                    "script={}",
                    json_str(&rec.value, "script_or_process").unwrap_or("?")
                ),
                format!("inputs={}", display_json_field(&rec.value, "inputs")),
            ),
            _ => (
                json_str(&rec.value, "label").unwrap_or("").to_string(),
                format!(
                    "related_claims={}",
                    display_json_field(&rec.value, "related_claims")
                ),
                format!(
                    "severity={} mitigation={}",
                    json_str(&rec.value, "severity").unwrap_or("?"),
                    json_str(&rec.value, "mitigation").unwrap_or("?")
                ),
            ),
        };
        lines.push(format!("## {} [{}]", rid, status));
        lines.push(head);
        lines.push(format!("- {}", links));
        lines.push(format!("- {}", extra));
        lines.push(format!("- cited_by={:?}", cited_by));
        lines.push(String::new());
    }
    lines.join("\n") + "\n"
}

fn display_json_field(rec: &Value, field: &str) -> String {
    rec.get(field)
        .cloned()
        .unwrap_or(Value::Array(Vec::new()))
        .to_string()
}

fn display_relations(rec: &Value) -> String {
    let Some(arr) = rec.get("relations").and_then(Value::as_array) else {
        return "[]".to_string();
    };
    let items: Vec<String> = arr
        .iter()
        .filter_map(|rel| {
            let t = rel.get("type")?.as_str()?;
            let target = rel.get("target")?.as_str()?;
            Some(format!("({}, {})", t, target))
        })
        .collect();
    format!("[{}]", items.join(", "))
}

fn fold(root: &Path) -> io::Result<Vec<PathBuf>> {
    let graph = load_all(root);
    let refs = backrefs(&graph);
    let mut written = Vec::new();
    for spec in CANON {
        let name = match spec.kind {
            "claim" => "claims_index.md",
            "evidence" => "evidence_index.md",
            "provenance" => "provenance_index.md",
            "lit_prop" => "lit_props_index.md",
            "data_registry" => "data_registry_index.md",
            "runs" => "runs_index.md",
            _ => "risks_index.md",
        };
        let dir = root.join(spec.dir);
        fs::create_dir_all(&dir)?;
        let path = dir.join(name);
        let text = fold_one(root, spec, refs.get(spec.kind).unwrap_or(&BTreeMap::new()));
        fs::write(&path, text)?;
        written.push(path);
    }
    Ok(written)
}

fn project_root(payload: Option<&Value>) -> PathBuf {
    if let Ok(root) = env::var("CLAUDE_PROJECT_DIR") {
        return PathBuf::from(root);
    }
    if let Some(cwd) = payload
        .and_then(|p| p.get("cwd"))
        .and_then(Value::as_str)
        .filter(|s| !s.is_empty())
    {
        return PathBuf::from(cwd);
    }
    env::current_dir().unwrap_or_else(|_| PathBuf::from("."))
}

fn parse_project_root(args: &[String]) -> PathBuf {
    let mut i = 0;
    while i < args.len() {
        if args[i] == "--project-root" {
            if let Some(value) = args.get(i + 1) {
                return PathBuf::from(value);
            }
        }
        i += 1;
    }
    project_root(None)
}

fn active_agent(payload: &Value) -> String {
    for key in ["CLAUDE_AGENT_NAME", "CLAUDE_SUBAGENT_NAME"] {
        if let Ok(value) = env::var(key) {
            if !value.is_empty() {
                return value;
            }
        }
    }
    for key in ["agent_name", "subagent_name"] {
        if let Some(value) = payload.get(key).and_then(Value::as_str) {
            if !value.is_empty() {
                return value.to_string();
            }
        }
    }
    if let Some(agent) = payload.get("agent") {
        if let Some(value) = agent.as_str() {
            return value.to_string();
        }
        if let Some(obj) = agent.as_object() {
            for key in ["name", "type"] {
                if let Some(value) = obj.get(key).and_then(Value::as_str) {
                    if !value.is_empty() {
                        return value.to_string();
                    }
                }
            }
        }
    }
    String::new()
}

fn canon_owner(root: &Path) -> String {
    let path = root.join(".project/policies/team-promotion.json");
    let Some(value) = read_json(&path) else {
        return "orchestrator".to_string();
    };
    let Some(gov) = value.get("governance").and_then(Value::as_object) else {
        return "orchestrator".to_string();
    };
    for key in ["company_owner", "authoring_owner"] {
        if let Some(owner) = gov.get(key).and_then(Value::as_str).map(str::trim) {
            if !owner.is_empty() {
                return owner.to_string();
            }
        }
    }
    "orchestrator".to_string()
}

fn touches_canon_path(root: &Path, raw: &str) -> bool {
    if raw.is_empty() {
        return false;
    }
    let mut path = PathBuf::from(raw.trim_matches('"').trim_matches('\''));
    if !path.is_absolute() {
        path = root.join(path);
    }
    let rel = path.strip_prefix(root).map(Path::to_path_buf).or_else(|_| {
        let root_abs = root.canonicalize().unwrap_or_else(|_| root.to_path_buf());
        let path_abs = path.canonicalize().unwrap_or_else(|_| path.clone());
        path_abs.strip_prefix(&root_abs).map(Path::to_path_buf)
    });
    let Ok(rel) = rel else {
        return false;
    };
    let rel_str = rel.to_string_lossy();
    rel.components().next().map(|c| c.as_os_str()) == Some(std::ffi::OsStr::new(".project"))
        && CANON.iter().any(|spec| {
            rel_str == spec.dir.trim_start_matches("./")
                || rel_str.starts_with(&format!("{}/", spec.dir.trim_start_matches("./")))
        })
}

fn raw_command_mentions_canon(command: &str) -> bool {
    CANON.iter().any(|spec| {
        let dir = spec.dir.trim_start_matches("./");
        command.contains(dir) || command.contains(&format!("./{}", dir))
    })
}

fn touches_canon(payload: &Value, root: &Path) -> bool {
    let tool = payload
        .get("tool_name")
        .and_then(Value::as_str)
        .unwrap_or("");
    let Some(input) = payload.get("tool_input").and_then(Value::as_object) else {
        return false;
    };
    if tool == "Bash" {
        let command = input
            .get("command")
            .or_else(|| input.get("cmd"))
            .and_then(Value::as_str)
            .unwrap_or("");
        let tokens: Vec<&str> = command.split_whitespace().collect();
        let has_mutation = tokens.iter().any(|t| {
            matches!(
                *t,
                ">" | ">>"
                    | "mv"
                    | "cp"
                    | "rm"
                    | "touch"
                    | "mkdir"
                    | "sed"
                    | "perl"
                    | "python"
                    | "python3"
                    | "node"
            ) || t.starts_with('>')
        });
        return has_mutation
            && (raw_command_mentions_canon(command)
                || tokens.iter().any(|t| touches_canon_path(root, t)));
    }
    let raw = input
        .get("file_path")
        .or_else(|| input.get("path"))
        .and_then(Value::as_str)
        .unwrap_or("");
    touches_canon_path(root, raw)
}

fn run_guard() -> i32 {
    let mut buf = String::new();
    if io::stdin().read_to_string(&mut buf).is_err() {
        return 0;
    }
    let Ok(payload) = serde_json::from_str::<Value>(&buf) else {
        return 0;
    };
    let tool = payload
        .get("tool_name")
        .and_then(Value::as_str)
        .unwrap_or("");
    if !["Edit", "Write", "MultiEdit", "NotebookEdit", "Bash"].contains(&tool) {
        return 0;
    }
    let root = project_root(Some(&payload));
    if !touches_canon(&payload, &root) {
        return 0;
    }
    let owner = canon_owner(&root);
    let agent = active_agent(&payload);
    if agent != owner {
        eprintln!(
            "Canon owner approval missing - only canon owner '{}' may write .project canon records (you are '{}').",
            owner,
            if agent.is_empty() { "unknown" } else { &agent }
        );
        return 2;
    }
    let result = validate(&root);
    if !result.errors.is_empty() {
        eprintln!("Canon integrity violation(s) - fix before writing:");
        for err in result.errors {
            eprintln!("  - {}", err);
        }
        return 2;
    }
    0
}

fn run_check(args: &[String]) -> i32 {
    let root = parse_project_root(args);
    let result = validate(&root);
    for warning in &result.warnings {
        println!("WARN  {}", warning);
    }
    for error in &result.errors {
        eprintln!("ERROR {}", error);
    }
    println!(
        "{} error(s) / {} warning(s)",
        result.errors.len(),
        result.warnings.len()
    );
    if result.errors.is_empty() { 0 } else { 1 }
}

fn run_fold(args: &[String]) -> i32 {
    let root = parse_project_root(args);
    match fold(&root) {
        Ok(paths) => {
            for path in paths {
                println!("folded -> {}", path.display());
            }
            0
        }
        Err(err) => {
            eprintln!("fold failed: {}", err);
            1
        }
    }
}

fn main() {
    let args: Vec<String> = env::args().skip(1).collect();
    let code = match args.first().map(String::as_str) {
        Some("check") => run_check(&args[1..]),
        Some("fold") => run_fold(&args[1..]),
        Some("guard") => run_guard(),
        _ => run_guard(),
    };
    std::process::exit(code);
}
