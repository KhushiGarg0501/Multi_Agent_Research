const supabaseClient = window.supabase.createClient(
    SUPABASE_URL,
    SUPABASE_PUBLISHABLE_KEY
);

console.log("RESEARCHLY SCRIPT LOADED");

window.addEventListener("beforeunload", () => {
    console.log("PAGE IS RELOADING OR NAVIGATING");
});


const $ = (selector, root=document) => root.querySelector(selector);
const $$ = (selector, root=document) => [...root.querySelectorAll(selector)];
let currentTopic = "";
let currentReport = "";
let isDemoSignedIn = false;
let currentUser = null;

// Save completed research to the logged-in user's history
async function saveResearchHistory(topic, mode, report, sources = []) {
    if (!currentUser) {
        console.log("Guest research: history not saved.");
        return;
    }

    try {
        const { data, error } = await supabaseClient
            .from("research_history")
            .insert([
                {
                    user_id: currentUser.id,
                    topic: topic,
                    mode: mode,
                    report: report,
                    sources: sources
                }
            ])
            .select()
            .single();

        if (error) throw error;

        console.log("Research history saved:", data.id);

        showToast("Research saved to your history!");

        loadResearchHistory();

    } catch (error) {
        console.error("History saving failed:", error);
        showToast("Research completed, but history could not be saved.");
    }
}

// Load the logged-in user's research history
async function loadResearchHistory() {
    const historyList = document.getElementById("research-history-list");

    if (!historyList) return;

    if (!currentUser) {
        historyList.innerHTML =
            '<p class="history-empty">Sign in to view your research history.</p>';
        return;
    }

    historyList.innerHTML =
        '<p class="history-empty">Loading history...</p>';

    try {
        const { data, error } = await supabaseClient
            .from("research_history")
            .select("*")
            .order("created_at", { ascending: false });

        if (error) throw error;

        historyList.innerHTML = "";

        if (!data || data.length === 0) {
            historyList.innerHTML =
                '<p class="history-empty">No saved research yet.</p>';
            return;
        }

        // Group research history by date
const groups = {
    "Today": [],
    "Yesterday": [],
    "Previous 7 Days": [],
    "Older": []
};

const now = new Date();

const todayValue = Date.UTC(
    now.getFullYear(),
    now.getMonth(),
    now.getDate()
);

data.forEach(item => {
    const date = new Date(item.created_at);

    const itemValue = Date.UTC(
        date.getFullYear(),
        date.getMonth(),
        date.getDate()
    );

    const daysAgo = Math.floor(
        (todayValue - itemValue) / 86400000
    );

    if (daysAgo <= 0) {
        groups["Today"].push(item);
    } else if (daysAgo === 1) {
        groups["Yesterday"].push(item);
    } else if (daysAgo <= 7) {
        groups["Previous 7 Days"].push(item);
    } else {
        groups["Older"].push(item);
    }
});

// Display each date group
Object.entries(groups).forEach(([groupName, items]) => {

    if (items.length === 0) return;

    const section = document.createElement("div");
    section.className = "history-date-group";

    const heading = document.createElement("div");
    heading.className = "history-date-heading";
    heading.textContent = groupName;

    section.appendChild(heading);

    items.forEach(item => {
        const wrapper = document.createElement("div");
        wrapper.className = "history-item-wrapper";

        const button = document.createElement("button");
        button.className = "history-item";
        button.textContent = item.topic;
        button.title = item.topic;

        button.addEventListener("click", () => {
            openHistoryReport(item);
        });

        const deleteButton = document.createElement("button");
        deleteButton.className = "history-delete";
        deleteButton.textContent = "×";
        deleteButton.title = "Delete this research";

        deleteButton.addEventListener("click", async (event) => {
            event.stopPropagation();
            await deleteResearchHistory(item.id);
        });

        wrapper.append(button, deleteButton);
        section.appendChild(wrapper);
    });

    historyList.appendChild(section);
});
                

    } catch (error) {
        console.error("History loading failed:", error);

        historyList.innerHTML =
            '<p class="history-empty">Unable to load history.</p>';
    }
}

// Delete a saved research record
async function deleteResearchHistory(id) {
    const confirmed = confirm(
        "Are you sure you want to delete this research?"
    );

    if (!confirmed) return;

    try {
        const { error } = await supabaseClient
            .from("research_history")
            .delete()
            .eq("id", id);

        if (error) throw error;

        showToast("Research deleted successfully!");

        await loadResearchHistory();

    } catch (error) {
        console.error("History deletion failed:", error);
        showToast("Unable to delete research.");
    }
}

// Open a previously saved research report
function openHistoryReport(item) {
    currentTopic = item.topic;
    currentReport = item.report;

    $("#home-view").classList.add("hidden");
    $("#workspace-view").classList.remove("hidden");

    $("#chat-welcome").classList.add("hidden");
    $("#conversation").innerHTML = "";

    addMessage("user", item.topic);

    const reportHTML = escapeHTML(item.report);

    addMessage(
        "assistant",
        `
        <div class="mock-report">
            <div class="report-meta">
                RESEARCHLY · SAVED REPORT
            </div>

            <h3>${escapeHTML(item.topic)}</h3>

            <div class="report-content"
                 style="white-space:pre-wrap;line-height:1.7">
                ${reportHTML}
            </div>

            <div class="report-meta">
                Saved on ${new Date(item.created_at).toLocaleString()}
            </div>

            <div class="report-actions">
                <button class="download-action" id="download-report">
                    ↓ Download report
                </button>
            </div>
        </div>
        `
    );

    $("#download-report").addEventListener("click", downloadReport);

    $("#chat-area").scrollTop = $("#chat-area").scrollHeight;
}

// Check the existing session when Researchly loads
async function checkAuthSession() {
    try {
        const { data, error } = await supabaseClient.auth.getSession();

        if (error) throw error;

        currentUser = data.session?.user || null;
        isDemoSignedIn = !!currentUser;

        updateAuthUI();
        loadResearchHistory();

        console.log("Authentication initialized:", currentUser?.email || "Guest");
    } catch (error) {
        console.error("Authentication initialization failed:", error);
    }
}

// Listen for login, logout and session changes
supabaseClient.auth.onAuthStateChange((event, session) => {
    currentUser = session?.user || null;
    isDemoSignedIn = !!currentUser;

    updateAuthUI();
    loadResearchHistory();
});

// Update the visible interface
function updateAuthUI() {
    const loggedIn = !!currentUser;

    // Homepage buttons
    $("#header-login").classList.toggle("hidden", loggedIn);
    $("#header-signup").classList.toggle("hidden", loggedIn);
    $("#header-account").classList.toggle("hidden", !loggedIn);
    $("#header-logout").classList.toggle("hidden", !loggedIn);

    // Workspace profile
    const profile = $(".sidebar-profile");

    if (profile) {
        if (loggedIn) {
            profile.innerHTML = `
                <span class="profile-avatar">👤</span>
                <span>
                    <b>${escapeHTML(currentUser.email)}</b>
                    <small>My account</small>
                </span>
                <span class="profile-arrow">↗</span>
            `;
        } else {
            profile.innerHTML = `
                <span class="profile-avatar">G</span>
                <span>
                    <b>Guest workspace</b>
                    <small>Sign in to save your work</small>
                </span>
                <span class="profile-arrow">↗</span>
            `;
        }
    }

    // Workspace status
    const secureNote = $(".secure-note");

    if (secureNote) {
        secureNote.innerHTML = loggedIn
            ? "<i></i> Signed in"
            : "<i></i> Guest session";
    }

    // Account details
    if (loggedIn) {
        $("#account-email").textContent = currentUser.email;
    }
}

// Run on page load
checkAuthSession();

let researchMode = "web";
let attachedPDFs = [];
const API_BASE = "http://127.0.0.1:8000";

function showToast(message){
  const toast = $("#toast");
  toast.textContent = message;
  toast.classList.add("show");
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(()=>toast.classList.remove("show"), 3000);
}
function openWorkspace() {
    console.log("OPEN WORKSPACE CALLED");

    $("#home-view").classList.add("hidden");
    $("#workspace-view").classList.remove("hidden");

    window.scrollTo(0, 0);
    setTimeout(() => $("#research-input").focus(), 80);
}

function goHome() {
    console.trace("GO HOME CALLED");

    alert("DEBUG: goHome() was called!");

    $("#workspace-view").classList.add("hidden");
    $("#home-view").classList.remove("hidden");

    window.scrollTo({ top: 0, behavior: "smooth" });
}
function openAuth(mode="login"){
  $("#auth-title").innerHTML = mode === "signup" ? "Create your<br><span class='gradient-text'>research space.</span>" : "Continue your<br><span class='gradient-text'>research journey.</span>";
  $("#auth-description").textContent = mode === "signup" ? "Create an account to keep your research conversations and reports together." : "Sign in to save your conversations and download your research reports.";
  $("#auth-modal").classList.remove("hidden");
}
function closeAuth(){ $("#auth-modal").classList.add("hidden"); }
function addMessage(kind, content){
  const row = document.createElement("div");
  row.className = `message ${kind}`;
  if(kind === "assistant"){
    row.innerHTML = `<span class="message-badge">✦</span><div class="message-body">${content}</div>`;
  } else {
    const body = document.createElement("div");
    body.className = "message-body";
    body.textContent = content;
    row.append(body);
  }
  $("#conversation").append(row);
  $("#chat-area").scrollTop = $("#chat-area").scrollHeight;
  return row;
}
function escapeHTML(value){
  return value.replace(/[&<>"']/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[char]));
}
function createPreviewReport(topic){
  const safe = escapeHTML(topic);
  currentReport = `Research topic: ${topic}\n\nThis is a frontend preview. Connect the Python research API to generate a real research report.\n\nSuggested research directions:\n1. Background and context\n2. Current developments and evidence\n3. Opportunities and challenges\n4. Key findings and future outlook\n\nGenerated by Researchly UI preview.`;
  return `<div class="mock-report"><div class="report-meta">RESEARCH OVERVIEW · PREVIEW RESPONSE</div><h3>Research brief: ${safe}</h3><p>This interface is currently running in preview mode. Once the Python API is connected, your multi-agent workflow will plan the research, search for sources, analyse relevant pages, write a report and review its quality.</p><p><strong>Suggested directions to explore</strong></p><ul><li>Background, context and key definitions</li><li>Recent developments and supporting evidence</li><li>Major opportunities, limitations and challenges</li><li>Key findings and possible future directions</li></ul><div class="report-actions"><button class="download-action" id="download-report">↓ Download report</button><button id="save-chat">＋ Save conversation</button></div></div>`;
}
async function runResearch(topic) {
  const clean = topic.trim();
  if (!clean) return;

  if (
    (researchMode === "pdf" || researchMode === "combined") &&
    attachedPDFs.length === 0
  ) {
    showToast("Add at least one PDF for this research mode.");
    $("#pdf-upload").click();
    return;
  }

  if (attachedPDFs.some(pdf => pdf.status !== "uploaded")) {
    showToast("Please wait until all PDFs finish uploading.");
    return;
  }

  const modeLabels = {
    web: "Web Search",
    pdf: "Ask My PDFs",
    combined: "Web + PDFs"
  };

  const apiModes = {
    web: "web_search",
    pdf: "ask_pdfs",
    combined: "combined"
  };

  const selectedFiles = [...attachedPDFs];
  currentTopic = clean;

  $("#chat-welcome").classList.add("hidden");

  const fileNote = selectedFiles.length
    ? `\n\nAttached PDFs: ${selectedFiles.map(pdf => pdf.name).join(", ")}`
    : "";

  addMessage(
    "user",
    `${clean}\n\nMode: ${modeLabels[researchMode]}${fileNote}`
  );

  const loading = addMessage(
    "assistant",
    `<div class="research-status">
      <span class="loading-dots"><i></i><i></i><i></i></span>
      Researching your topic. This may take a little while…
    </div>`
  );

  $("#research-input").value = "";

  try {
    const response = await fetch(`${API_BASE}/api/research`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        topic: clean,
        mode: apiModes[researchMode],
        selected_document_ids: selectedFiles.map(
          pdf => pdf.document_id
        )
      })
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || "Research request failed.");
    }

    const resultText = data.report || data.answer || "";

    if (!resultText) {
      throw new Error("The backend returned an empty research result.");
    }

    currentReport = resultText;

    await saveResearchHistory(
        clean,
        apiModes[researchMode],
        resultText,
        data.sources || []
    );

    const safeResult = escapeHTML(resultText);

    let sourcesHTML = "";

    if (data.sources && data.sources.length) {
      sourcesHTML = `
        <h4>PDF Sources</h4>
        <ul>
          ${data.sources.map(source => `
            <li>
              ${escapeHTML(String(source.filename || "PDF"))}
              — Page ${escapeHTML(String(source.page || "N/A"))}
            </li>
          `).join("")}
        </ul>
      `;
    }

    loading.querySelector(".message-body").innerHTML = `
      <div class="mock-report">
        <div class="report-meta">
          RESEARCHLY · ${escapeHTML(modeLabels[researchMode].toUpperCase())}
        </div>

        <h3>Research results</h3>

        <div class="report-content" style="white-space:pre-wrap;line-height:1.7">
          ${safeResult}
        </div>

        ${sourcesHTML}

        <div class="report-actions">
          <button class="download-action" id="download-report">
            ↓ Download report
          </button>
          <button id="save-chat">＋ Save conversation</button>
        </div>
      </div>
    `;

    $("#download-report").addEventListener("click", downloadReport);
    $("#save-chat").addEventListener("click", () => openAuth("signup"));

    $("#chat-area").scrollTop = $("#chat-area").scrollHeight;

    showToast("Research completed successfully!");

  } catch (error) {
    loading.querySelector(".message-body").innerHTML = `
      <div class="research-error">
        <h3>Research could not be completed</h3>
        <p>${escapeHTML(error.message)}</p>
        <p>Please try again.</p>
      </div>
    `;

    showToast(error.message);
    console.error("Research API error:", error);
  }
}
function downloadReport(){
  if(!isDemoSignedIn){ openAuth("login"); showToast("Sign in is required to download a report."); return; }
  const blob = new Blob([currentReport], {type:"text/plain;charset=utf-8"});
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url; anchor.download = "researchly-research-report.txt"; anchor.click();
  URL.revokeObjectURL(url);
  showToast("Preview report downloaded.");
}

$("#hero-start").addEventListener("click", openWorkspace);
$("#workflow-start").addEventListener("click", openWorkspace);
$("#bottom-start").addEventListener("click", openWorkspace);
$$("[data-home]").forEach(el=>el.addEventListener("click", event=>{event.preventDefault();goHome()}));
$$("[data-auth]:not(.sidebar-profile)").forEach(el => {
    el.addEventListener("click", () => openAuth(el.dataset.auth));
});
$("#research-form").addEventListener("submit", event=>{event.preventDefault();runResearch($("#research-input").value)});
$$("[data-prompt]").forEach(el=>el.addEventListener("click", ()=>runResearch(el.dataset.prompt)));
$("#new-chat").addEventListener("click", ()=>{
  $("#conversation").innerHTML = "";
  attachedPDFs = [];
  renderAttachedPDFs();
  $("#chat-welcome").classList.remove("hidden");
  $("#research-input").value = "";
  currentTopic = ""; currentReport = "";
  showToast("Started a new research session.");
});
$("#modal-close").addEventListener("click", closeAuth);
$("#auth-modal").addEventListener("click", event=>{if(event.target === $("#auth-modal")) closeAuth()});
$("#google-demo").addEventListener("click", async () => {
    try {
        const { data, error } = await supabaseClient.auth.signInWithOAuth({
            provider: "google",
            options: {
                redirectTo: window.location.origin + "/frontend/"
            }
        });

        if (error) {
            console.error("Google sign-in error:", error);
            showToast(error.message);
        }
    } catch (error) {
        console.error(error);
        showToast("Unable to sign in. Please try again.");
    }
});
$("#email-demo").addEventListener("click", ()=>{
  showToast("Account creation will be connected during the authentication stage.");
});
const menuButton = $(".mobile-menu");
menuButton.addEventListener("click", ()=>{
  const nav = $(".main-nav");
  const open = nav.classList.toggle("open");
  menuButton.setAttribute("aria-expanded", String(open));
});
// Make the homepage navigation reliably scroll to its matching section.
$$(".main-nav a").forEach(link => {
  link.addEventListener("click", event => {
    const targetId = link.getAttribute("href");
    const target = targetId ? document.querySelector(targetId) : null;
    event.preventDefault();
    $(".main-nav").classList.remove("open");
    menuButton.setAttribute("aria-expanded", "false");
    if (target) {
      // If the user is in the research workspace, return to the homepage first.
      if ($("#home-view").classList.contains("hidden")) goHome();
      requestAnimationFrame(() => {
        target.scrollIntoView({ behavior: "smooth", block: "start" });
        history.replaceState(null, "", targetId);
      });
    }
  });
});
const modeLabels = {web:"Web Search",pdf:"Ask My PDFs",combined:"Web + PDFs"};
const modeDescriptions = {web:"Web research",pdf:"Your PDFs",combined:"Web + PDF research"};
$$(".mode-button").forEach(button=>{
  button.addEventListener("click", ()=>{
    researchMode = button.dataset.mode;
    $$(".mode-button").forEach(item=>{
      const active = item === button;
      item.classList.toggle("active", active);
      item.setAttribute("aria-pressed", String(active));
    });
    $("#composer-mode-label").innerHTML = `<span class="composer-spark">✦</span> ${modeDescriptions[researchMode]}`;
    $("#research-input").placeholder = researchMode === "pdf"
      ? "Ask a question about your PDFs..."
      : researchMode === "combined"
        ? "Research across the web and your PDFs..."
        : "Ask anything you want to research...";
    if(researchMode !== "web" && attachedPDFs.length === 0){
      showToast("Use the + button to attach one or more PDFs.");
    }
  });
});
function renderAttachedPDFs() {
  const wrap = $("#attached-files");
  wrap.innerHTML = "";

  if (!attachedPDFs.length) {
    wrap.classList.add("hidden");
    return;
  }

  wrap.classList.remove("hidden");

  attachedPDFs.forEach((pdf, index) => {
    const chip = document.createElement("span");
    chip.className = "file-chip";

    const name = document.createElement("span");
    name.textContent =
      pdf.name + (pdf.status === "uploading" ? " (Uploading...)" :
      pdf.status === "uploaded" ? " ✓" : " (Failed)");

    const remove = document.createElement("button");
    remove.type = "button";
    remove.textContent = "×";
    remove.setAttribute("aria-label", `Remove ${pdf.name}`);

    remove.addEventListener("click", () => {
      attachedPDFs.splice(index, 1);
      renderAttachedPDFs();
    });

    chip.append(name, remove);
    wrap.append(chip);
  });
}
$("#attach-pdf").addEventListener("click", (event) => {
  event.preventDefault();
  $("#pdf-upload").click();
});
$("#pdf-upload").addEventListener("change", async event => {
  console.log("PDF CHANGE EVENT FIRED");
  const chosen = [
    ...event.target.files
  ].filter(file =>
    file.type === "application/pdf" ||
    file.name.toLowerCase().endsWith(".pdf")
  );

  event.target.value = "";

  if (!chosen.length) {
    showToast("Please select a PDF file.");
    return;
  }

  for (const file of chosen) {
    const alreadyAdded = attachedPDFs.some(
      pdf => pdf.name === file.name && pdf.size === file.size
    );

    if (alreadyAdded) continue;

    const pdfItem = {
      name: file.name,
      size: file.size,
      document_id: null,
      status: "uploading"
    };

    attachedPDFs.push(pdfItem);
    renderAttachedPDFs();

    try {
      const formData = new FormData();
      formData.append("file", file);

      const response = await fetch(`${API_BASE}/api/upload-pdf`, {
        method: "POST",
        body: formData
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "PDF upload failed.");
      }

      pdfItem.document_id = data.document_id;
      pdfItem.status = "uploaded";

      showToast(`${file.name} uploaded successfully.`);

    } catch (error) {
      pdfItem.status = "failed";
      console.error("PDF upload error:", error);
      showToast(`Upload failed: ${error.message}`);
    }

    renderAttachedPDFs();
  }
});
$("#research-input").addEventListener("keydown", event=>{
  if(event.key === "Enter" && !event.shiftKey){event.preventDefault();$("#research-form").requestSubmit()}
});


document.addEventListener("DOMContentLoaded", () => {
    checkAuthSession();
});


// Open account modal
function openAccount() {
    if (!currentUser) {
        openAuth("login");
        return;
    }

    $("#account-modal").classList.remove("hidden");
}

// Close account modal
$("#account-close").addEventListener("click", () => {
    $("#account-modal").classList.add("hidden");
});

// Homepage account button
$("#header-account").addEventListener("click", openAccount);

// Workspace profile button
$(".sidebar-profile").addEventListener("click", openAccount);

// Logout function
async function logoutUser() {
    const { error } = await supabaseClient.auth.signOut();

    if (error) {
        showToast(error.message);
        return;
    }

    currentUser = null;
    isDemoSignedIn = false;

    updateAuthUI();

    $("#account-modal").classList.add("hidden");
    closeAuth();

    showToast("You have been logged out successfully.");
}

// Logout buttons
$("#header-logout").addEventListener("click", logoutUser);
$("#account-logout").addEventListener("click", logoutUser);