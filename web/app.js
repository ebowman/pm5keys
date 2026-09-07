// pm5keys web demo: loads Pyodide, installs the pm5keys wheel, and
// calls into Python to parse + compile workout text entirely in the
// browser. No LLM, no server round-trip.
"use strict";

const statusLine = document.getElementById("status-line");
const generateBtn = document.getElementById("generate-btn");
const textArea = document.getElementById("workout-text");
const chipsContainer = document.getElementById("example-chips");
const outputPanel = document.getElementById("output-panel");
const outputLines = document.getElementById("output-lines");
const traceContent = document.getElementById("trace-content");
const traceDetails = document.getElementById("trace-details");

let pyodideReady = null;
let pyGenerate = null;

function setStatus(message, kind) {
  statusLine.textContent = message;
  statusLine.classList.remove("error", "ready");
  if (kind) {
    statusLine.classList.add(kind);
  }
  console.log("[pm5keys]", message);
}

function getSelectedMonitor() {
  const checked = document.querySelector('input[name="monitor"]:checked');
  return checked ? checked.value : "both";
}

function renderChips() {
  const examples =
    typeof PM5KEYS_EXAMPLES !== "undefined" ? PM5KEYS_EXAMPLES : [];
  chipsContainer.innerHTML = "";
  examples.forEach((title) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "chip";
    btn.textContent = title;
    btn.addEventListener("click", () => {
      textArea.value = title;
      textArea.focus();
    });
    chipsContainer.appendChild(btn);
  });
}

function formatTrace(trace) {
  // trace: array of [press, screen, action]
  if (!trace || trace.length === 0) {
    return "";
  }
  const pressWidth = Math.max(...trace.map((row) => String(row[0]).length));
  const screenWidth = Math.max(...trace.map((row) => String(row[1]).length));
  return trace
    .map((row) => {
      const press = String(row[0]).padEnd(pressWidth);
      const screen = String(row[1]).padEnd(screenWidth);
      const action = String(row[2]);
      return `${press}  ${screen}: ${action}`;
    })
    .join("\n");
}

function renderResult(result) {
  outputPanel.hidden = false;

  if (!result.ok) {
    outputLines.textContent = "";
    traceContent.textContent = "";
    setStatus(result.error || "unparsed", "error");
    outputPanel.hidden = true;
    return;
  }

  outputLines.textContent = result.lines.join("\n");

  const pieces = [];
  if (result.explains.pm3 && result.explains.pm3.length) {
    pieces.push("PM3/PM4:\n" + formatTrace(result.explains.pm3));
  }
  if (result.explains.pm5 && result.explains.pm5.length) {
    pieces.push("PM5:\n" + formatTrace(result.explains.pm5));
  }
  traceContent.textContent = pieces.join("\n\n");

  setStatus("Ready", "ready");
}

async function runGenerate() {
  const text = textArea.value;
  const monitor = getSelectedMonitor();

  if (!pyGenerate) {
    setStatus("Python runtime still loading, please wait…");
    return;
  }

  console.log("[pm5keys] generate()", { text, monitor });
  try {
    const raw = pyGenerate(text, monitor);
    const result = JSON.parse(raw);
    console.log("[pm5keys] result", result);
    renderResult(result);
  } catch (err) {
    console.error("[pm5keys] generate() failed", err);
    outputPanel.hidden = true;
    setStatus("Internal error: " + err, "error");
  }
}

async function loadPyodideAndPackage() {
  setStatus("Loading Python runtime… (about 10 MB, first visit only)");

  const pyodide = await loadPyodide();
  console.log("[pm5keys] Pyodide loaded");

  setStatus("Installing pm5keys…");
  await pyodide.loadPackage("micropip");
  const micropip = pyodide.pyimport("micropip");

  const version =
    typeof PM5KEYS_VERSION !== "undefined" ? PM5KEYS_VERSION : "0.1.0";
  const wheelUrl = `./dist/pm5keys-${version}-py3-none-any.whl`;

  console.log("[pm5keys] installing wheel from", wheelUrl);
  await micropip.install(wheelUrl);

  const workerSrc = await (await fetch("./pyworker.py")).text();
  pyodide.runPython(workerSrc);
  pyGenerate = pyodide.globals.get("generate");

  setStatus("Ready", "ready");
  generateBtn.disabled = false;
  console.log("[pm5keys] ready");
}

renderChips();

generateBtn.addEventListener("click", runGenerate);

pyodideReady = loadPyodideAndPackage().catch((err) => {
  console.error("[pm5keys] failed to load Python runtime", err);
  setStatus(
    "Failed to load Python runtime: " + err + " -- try reloading the page.",
    "error"
  );
});
