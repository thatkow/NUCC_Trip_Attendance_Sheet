
const tutorialOverlay = document.getElementById("tutorial-overlay");
const tutorialCloseButton = document.getElementById("tutorial-close");
const tutorialVideo = document.getElementById("tutorial-video");

function hideTutorialOverlay() {
    if (!tutorialOverlay) return;
    tutorialOverlay.classList.add("is-hidden");
    if (tutorialVideo) {
        tutorialVideo.pause();
        tutorialVideo.currentTime = 0;
    }
}

if (tutorialOverlay) {
    window.addEventListener("load", () => {
        tutorialOverlay.classList.remove("is-hidden");
        if (tutorialCloseButton) {
            tutorialCloseButton.focus();
        }
    });

    tutorialOverlay.addEventListener("click", (event) => {
        if (event.target === tutorialOverlay) {
            hideTutorialOverlay();
        }
    });
}

if (tutorialCloseButton) {
    tutorialCloseButton.addEventListener("click", hideTutorialOverlay);
}

document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && tutorialOverlay && !tutorialOverlay.classList.contains("is-hidden")) {
        hideTutorialOverlay();
    }
});

const nameListId = "member-options";
const nameDatalist = document.createElement("datalist");
nameDatalist.id = nameListId;
document.body.appendChild(nameDatalist);

const tripLeaderListId = "trip-leader-options";
const tripLeaderDatalist = document.createElement("datalist");
tripLeaderDatalist.id = tripLeaderListId;
document.body.appendChild(tripLeaderDatalist);

const tripLeaderInput = document.getElementById("trip-leader");
const clerkInput = document.getElementById("clerk");
const tripDateInput = document.getElementById("trip-date");
const tripLocationInput = document.getElementById("trip-location");

if (tripLeaderInput) {
    tripLeaderInput.setAttribute("list", tripLeaderListId);
}

if (clerkInput) {
    clerkInput.setAttribute("list", tripLeaderListId);
}

if (tripDateInput) {
    tripDateInput.addEventListener("input", () => {
        renderBankingDetails();
    });
}

if (tripLocationInput) {
    tripLocationInput.addEventListener("input", () => {
        renderBankingDetails();
    });
}

let memberNames = [];
let bankingDetailsData = null;

const baseExpenseRates = {
    "personal-gear": 5,
    "shared-gear": 5
};

const baseExpenseKeys = Object.keys(baseExpenseRates);

const participants = Array.from({ length: 10 }, () => ({
    name: "",
    bold: false,
    notes: ""
}));

const baseExpenseDefinitions = [
    {
        key: "personal-gear",
        name: "Personal Gear",
        enabled: true,
        defaultConsumerState: false
    },
    {
        key: "shared-gear",
        name: "Shared Gear",
        enabled: true,
        defaultConsumerState: false
    },
    { key: "petrol", name: "Petrol", enabled: true, defaultConsumerState: true }
];

const sharedGearMasterToggle = document.getElementById(
    "shared-gear-master-toggle"
);

let customExpenseCounter = 0;

function createExpense({
    name,
    key = null,
    type = "custom",
    enabled = true,
    defaultConsumerState = true
}) {
    const id = type === "base" ? `base-${key}` : `custom-${customExpenseCounter++}`;
    return {
        id,
        name,
        key,
        type,
        enabled,
        defaultConsumerState,
        amounts: participants.map(() => ""),
        consumers: participants.map(() => defaultConsumerState)
    };
}

const baseExpenses = baseExpenseDefinitions.map((definition) =>
    createExpense({ ...definition, type: "base" })
);

const customExpenses = [];

if (tripDateInput && !tripDateInput.value) {
    const now = new Date();
    now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
    tripDateInput.value = now.toISOString().slice(0, 10);
}

const baseExpenseRateInputs = {
    "personal-gear": document.getElementById("personal-gear-rate"),
    "shared-gear": document.getElementById("shared-gear-rate")
};

baseExpenseKeys.forEach((key) => {
    applyBaseExpenseRateToExpense(key);
});

function isBaseRateControlled(expense) {
    if (!expense || !expense.key) {
        return false;
    }
    return Object.prototype.hasOwnProperty.call(baseExpenseRates, expense.key);
}

function isDirectChargeExpense(expense) {
    if (!expense) {
        return false;
    }
    return expense.key === "personal-gear" || expense.key === "shared-gear";
}

function applyBaseExpenseRateToExpense(key) {
    const expense = baseExpenses.find((item) => item.key === key);
    if (!expense) {
        return;
    }
    ensureExpenseSize(expense);
    const rate = baseExpenseRates[key];
    for (let index = 0; index < expense.amounts.length; index += 1) {
        expense.amounts[index] = rate === "" ? "" : rate;
    }
}

function syncBaseExpenseInputsFromRates() {
    baseExpenseKeys.forEach((key) => {
        const input = baseExpenseRateInputs[key];
        if (!input) {
            return;
        }
        const value = baseExpenseRates[key];
        input.value = value === "" ? "" : String(value);
    });
}

function updateDuplicateNameWarnings() {
    const nameInputs = Array.from(document.querySelectorAll(".name-input"));
    const warningElement = document.getElementById("duplicate-name-warning");
    const counts = new Map();

    nameInputs.forEach((input) => {
        const normalized = input.value.trim().toLowerCase();
        if (!normalized) {
            return;
        }
        counts.set(normalized, (counts.get(normalized) || 0) + 1);
    });

    const duplicateKeys = new Set();
    counts.forEach((count, key) => {
        if (count > 1) {
            duplicateKeys.add(key);
        }
    });

    nameInputs.forEach((input) => {
        const normalized = input.value.trim().toLowerCase();
        if (normalized && duplicateKeys.has(normalized)) {
            input.classList.add("duplicate-name");
            input.setAttribute("aria-invalid", "true");
        } else {
            input.classList.remove("duplicate-name");
            input.removeAttribute("aria-invalid");
        }
    });

    if (warningElement) {
        if (duplicateKeys.size > 0) {
            const labels = [];
            duplicateKeys.forEach((key) => {
                const matchingInput = nameInputs.find(
                    (input) => input.value.trim().toLowerCase() === key
                );
                if (matchingInput) {
                    const trimmed = matchingInput.value.trim();
                    if (trimmed && !labels.includes(trimmed)) {
                        labels.push(trimmed);
                    }
                }
            });
            warningElement.hidden = false;
            warningElement.textContent = `Duplicate names detected: ${labels.join(", ")}`;
        } else {
            warningElement.hidden = true;
            warningElement.textContent = "";
        }
    }
}

baseExpenseKeys.forEach((key) => {
    const input = baseExpenseRateInputs[key];
    if (!input) {
        return;
    }
    input.addEventListener("input", () => {
        const rawValue = input.value;
        if (rawValue === "") {
            baseExpenseRates[key] = "";
            applyBaseExpenseRateToExpense(key);
            renderTable();
            syncBaseExpenseInputsFromRates();
            return;
        }
        const numericValue = Number(rawValue);
        if (!Number.isFinite(numericValue)) {
            return;
        }
        baseExpenseRates[key] = numericValue;
        applyBaseExpenseRateToExpense(key);
        renderTable();
        syncBaseExpenseInputsFromRates();
    });
});

function getAllExpenses() {
    return [...baseExpenses, ...customExpenses];
}

function getActiveExpenses() {
    return [
        ...baseExpenses.filter((expense) => expense.enabled),
        ...customExpenses
    ];
}

function getSharedGearExpense() {
    return baseExpenses.find((expense) => expense.key === "shared-gear");
}

function findExpenseById(id) {
    return getAllExpenses().find((expense) => expense.id === id);
}

function populateNameSelect(selectElement) {
    selectElement.innerHTML = "";

    const placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent = "";
    placeholder.setAttribute("aria-hidden", "true");
    selectElement.appendChild(placeholder);

    memberNames.forEach((name) => {
        const option = document.createElement("option");
        option.value = name;
        option.textContent = name;
        selectElement.appendChild(option);
    });

    selectElement.value = "";
}

function cloneNodeWithFormValues(node) {
    const clone = node.cloneNode(true);
    const originals = node.querySelectorAll("input, textarea, select");
    const clones = clone.querySelectorAll("input, textarea, select");
    originals.forEach((element, index) => {
        const cloned = clones[index];
        if (!cloned) {
            return;
        }
        if (cloned.tagName === "INPUT") {
            const input = element;
            const cloneInput = cloned;
            if (input.type === "checkbox" || input.type === "radio") {
                cloneInput.checked = input.checked;
                if (input.checked) {
                    cloneInput.setAttribute("checked", "");
                } else {
                    cloneInput.removeAttribute("checked");
                }
            } else {
                cloneInput.value = input.value;
                if (input.value === "") {
                    cloneInput.removeAttribute("value");
                } else {
                    cloneInput.setAttribute("value", input.value);
                }
            }
        } else if (cloned.tagName === "TEXTAREA") {
            cloned.value = element.value;
            cloned.textContent = element.value;
        } else if (cloned.tagName === "SELECT") {
            cloned.value = element.value;
            const selectedValues = Array.from(element.options)
                .filter((option) => option.selected)
                .map((option) => option.value);
            cloned.querySelectorAll("option").forEach((option) => {
                const isSelected = selectedValues.includes(option.value);
                option.selected = isSelected;
                if (isSelected) {
                    option.setAttribute("selected", "");
                } else {
                    option.removeAttribute("selected");
                }
            });
        }
    });
    return clone;
}

function stripIds(node) {
    if (node.nodeType === Node.ELEMENT_NODE) {
        node.removeAttribute("id");
        node
            .querySelectorAll("[id]")
            .forEach((element) => element.removeAttribute("id"));
    }
    return node;
}

function sanitizeSummaryClone(node) {
    node
        .querySelectorAll(
            ".expense-toggle-group, .base-expense-inputs, .controls, button"
        )
        .forEach((element) => element.remove());

    node.querySelectorAll('input[type="checkbox"]').forEach((checkbox) => {
        const replacement = node.ownerDocument.createElement("span");
        replacement.className = "summary-check";
        replacement.textContent = checkbox.checked ? "✔" : "";
        checkbox.replaceWith(replacement);
    });

    node.querySelectorAll("textarea").forEach((textarea) => {
        const display = node.ownerDocument.createElement("div");
        const classes = ["summary-multiline"];
        const existingClasses = textarea.className.trim();
        if (existingClasses) {
            classes.push(
                ...existingClasses
                    .split(/\s+/)
                    .filter((className) => className.length > 0)
            );
        }
        display.className = classes.join(" ");
        display.textContent = textarea.value || textarea.textContent || "";
        textarea.replaceWith(display);
    });

    node.querySelectorAll("select").forEach((select) => {
        const display = node.ownerDocument.createElement("span");
        const classes = ["summary-select"];
        const existingClasses = select.className.trim();
        if (existingClasses) {
            classes.push(
                ...existingClasses
                    .split(/\s+/)
                    .filter((className) => className.length > 0)
            );
        }
        display.className = classes.join(" ");

        const selectedOptions = Array.from(select.selectedOptions || []);
        const textContent = selectedOptions.length
            ? selectedOptions
                .map((option) => (option.textContent || "").trim())
                .filter((text) => text.length > 0)
                .join(", ")
            : select.value || "";
        display.textContent = textContent;
        select.replaceWith(display);
    });

    node.querySelectorAll("input").forEach((input) => {
        if (input.type === "checkbox") {
            return;
        }
        const display = node.ownerDocument.createElement("span");
        const classes = ["summary-value"];
        if (input.type === "number") {
            classes.push("summary-number");
        }
        const existingClasses = input.className.trim();
        if (existingClasses) {
            classes.push(
                ...existingClasses
                    .split(/\s+/)
                    .filter((className) => className.length > 0)
            );
        }
        display.className = classes.join(" ");
        let textContent = input.value || "";
        if (input.type === "number") {
            const { expenseId } = input.dataset || {};
            if (expenseId) {
                const numericValue = Number(input.value);
                if (Number.isFinite(numericValue) && input.value !== "") {
                    textContent = `$${formatCurrency(numericValue)}`;
                } else {
                    textContent = "";
                }
            }
        }
        display.textContent = textContent;
        input.replaceWith(display);
    });

    return node;
}

function removeEmptySummaryNameRows(node) {
    node
        .querySelectorAll(".attendance-table tbody tr")
        .forEach((row) => {
            const nameElement =
                row.querySelector(".name-input") || row.querySelector("td");
            const textContent =
                (nameElement?.textContent || "").replace(/\s+/g, " ").trim();
            if (!textContent) {
                row.remove();
            }
        });
    return node;
}

function formatSummaryDate(rawValue) {
    if (!rawValue) {
        return "";
    }

    const parsed = new Date(rawValue);
    if (Number.isNaN(parsed.getTime())) {
        return rawValue;
    }

    try {
        return new Intl.DateTimeFormat(undefined, { dateStyle: "long" }).format(
            parsed
        );
    } catch (error) {
        return rawValue;
    }
}

function buildSummaryPreview(targetDocument) {
    const container = targetDocument.createElement("div");
    container.className = "summary-preview";

    const summaryDescription = targetDocument.createElement("div");
    summaryDescription.className = "summary-description";

    const tripLocationValue = (tripLocationInput?.value || "").trim();
    const tripLeaderValue = (tripLeaderInput?.value || "").trim();
    const formattedDate = formatSummaryDate(tripDateInput?.value || "");
    const dateValue = formattedDate || tripDateInput?.value || "";

    const descriptionSegments = ["Cost accounting for"];
    if (tripLocationValue) {
        descriptionSegments.push(tripLocationValue);
    } else {
        descriptionSegments.push("this trip");
    }

    if (dateValue) {
        descriptionSegments.push(`on ${dateValue}`);
    }

    const descriptionParagraph = targetDocument.createElement("p");
    descriptionParagraph.textContent = `${descriptionSegments.join(" ")} for various expenses shown below.`;

    const leaderParagraph = targetDocument.createElement("p");
    leaderParagraph.className = "summary-line-gold";
    leaderParagraph.textContent = tripLeaderValue
        ? `Trip leader ${tripLeaderValue} should present this trip attendance summary to participants for review and confirmation of expenses. Once verified, a copy of the Trip Attendance Sheet should be sent to the treasurer to record dues and process reimbursements.`
        : "Trip leader should present this trip attendance summary to participants for review and confirmation of expenses. Once verified, a copy of the Trip Attendance Sheet should be sent to the treasurer to record dues and process reimbursements.";

    const reimburseParagraph = targetDocument.createElement("p");
    reimburseParagraph.className = "summary-line-green";
    reimburseParagraph.textContent =
        "Those with Reimburse values, colored green, will receive payment from the club account.";

    const oweParagraph = targetDocument.createElement("p");
    oweParagraph.className = "summary-line-red";
    oweParagraph.textContent =
        "If you owe, colored red in the Reimburse(Due), please pay to the club account details of which are provided in the top right.";

    summaryDescription.appendChild(descriptionParagraph);
    summaryDescription.appendChild(leaderParagraph);
    summaryDescription.appendChild(reimburseParagraph);
    summaryDescription.appendChild(oweParagraph);

    const sharedGearParagraph = targetDocument.createElement("p");
    sharedGearParagraph.textContent =
        "Shared gear refers to equipment that is used collectively by all members, which is common for vertical caving trips requiring SRT (Single Rope Technique) and for canyoning trips.";

    const personalGearParagraph = targetDocument.createElement("p");
    personalGearParagraph.textContent =
        "Personal gear refers to equipment intended for individual use, which may include any of the following: a personal SRT kit, helmet, overalls, or headtorch.";

    const petrolParagraph = targetDocument.createElement("p");
    petrolParagraph.textContent =
        "Petrol expenses are reported by the drivers after the trip. The total petrol costs are then pooled and divided equally among all participants to ensure fair sharing of travel expenses, regardless of who provided the vehicle.";

    const versionParagraph = targetDocument.createElement("p");
    versionParagraph.className = "summary-version";
    versionParagraph.textContent =
        "Version: In use from 28 Oct 2024 – 28 Oct 2025";

    summaryDescription.appendChild(sharedGearParagraph);
    summaryDescription.appendChild(personalGearParagraph);
    summaryDescription.appendChild(petrolParagraph);
    summaryDescription.appendChild(versionParagraph);

    const summaryTextWrapper = targetDocument.createElement("div");
    summaryTextWrapper.className = "summary-description-text";
    while (summaryDescription.firstChild) {
        summaryTextWrapper.appendChild(summaryDescription.firstChild);
    }
    summaryDescription.appendChild(summaryTextWrapper);

    const sections = [];
    const topSection = document.querySelector(".top-section");
    if (topSection) {
        sections.push(topSection);
    }
    const attendanceTable = document.getElementById("attendance-table");
    if (attendanceTable) {
        sections.push(attendanceTable);
    }
    const summarySection = document.querySelector("section");
    if (summarySection) {
        sections.push(summarySection);
    }

    let descriptionInserted = false;

    sections.forEach((section) => {
        const clone = stripIds(cloneNodeWithFormValues(section));
        if (!clone) {
            return;
        }
        sanitizeSummaryClone(clone);
        removeEmptySummaryNameRows(clone);
        const imported = targetDocument.importNode(clone, true);

        if (!descriptionInserted && section === topSection) {
            const metaTable = imported.querySelector(".meta-table");
            if (metaTable) {
                metaTable.insertAdjacentElement("afterend", summaryDescription);
            } else {
                imported.insertBefore(summaryDescription, imported.firstChild);
            }
            const minerImage = imported.querySelector(".miner-image");
            if (minerImage) {
                summaryDescription.appendChild(minerImage);
            }
            descriptionInserted = true;
        }
        container.appendChild(imported);
    });

    if (!descriptionInserted) {
        container.insertBefore(summaryDescription, container.firstChild);
    }

    return container;
}

function buildSummaryHtml(summaryTitle) {
    const summaryDocument = document.implementation.createHTMLDocument("");
    const resolvedTitle = summaryTitle || getDateLocationTag();
    summaryDocument.title = resolvedTitle;

    const metaCharset = summaryDocument.createElement("meta");
    metaCharset.setAttribute("charset", "utf-8");
    summaryDocument.head.appendChild(metaCharset);

    const baseHref = summaryDocument.createElement("base");
    baseHref.href = document.baseURI;
    summaryDocument.head.appendChild(baseHref);

    const existingStyle = document.querySelector("style");
    if (existingStyle) {
        summaryDocument.head.appendChild(
            summaryDocument.importNode(existingStyle, true)
        );
    }

    const extraStyle = summaryDocument.createElement("style");
    extraStyle.textContent = `
    .summary-check {
        display: inline-block;
        min-width: 1.5rem;
        text-align: center;
        font-weight: 600;
    }

    .summary-preview .top-section-right {
        flex: 0 0 15%;
        max-width: 15%;
        min-width: 0;
    }

    .summary-preview .top-section-right-inner {
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 1rem;
    }

    .summary-preview .banking-info {
        width: 100%;
    }

    .summary-preview .summary-description {
        display: flex;
        align-items: flex-start;
        gap: 1.5rem;
    }

    .summary-preview .summary-description-text {
        flex: 1 1 0;
    }

    .summary-preview .summary-description .miner-image {
        flex: 0 0 auto;
        max-width: clamp(160px, 25%, 220px);
        height: auto;
    }
    `;
    summaryDocument.head.appendChild(extraStyle);

    const main = summaryDocument.createElement("main");
    main.appendChild(buildSummaryPreview(summaryDocument));
    summaryDocument.body.appendChild(main);

    return `<!DOCTYPE html>${summaryDocument.documentElement.outerHTML}`;
}

function downloadAndOpenSummaryHtml() {
    const summaryTitle = getDateLocationTag();
    const htmlContent = buildSummaryHtml(summaryTitle);
    const blob = new Blob([htmlContent], { type: "text/html" });
    const url = URL.createObjectURL(blob);

    const downloadLink = document.createElement("a");
    downloadLink.href = url;
    downloadLink.download = `${summaryTitle}.html`;
    document.body.appendChild(downloadLink);
    downloadLink.click();
    document.body.removeChild(downloadLink);

    const summaryWindow = window.open("", "_blank");
    if (!summaryWindow) {
        window.alert("Please allow pop-ups to view the summary.");
        URL.revokeObjectURL(url);
        return;
    }

    summaryWindow.document.open();
    summaryWindow.document.write(htmlContent);
    summaryWindow.document.close();

    const ensureSummaryWindowTitle = () => {
        try {
            summaryWindow.document.title = summaryTitle;
        } catch (error) {
            /* no-op */
        }
    };

    ensureSummaryWindowTitle();

    if (typeof summaryWindow.addEventListener === "function") {
        summaryWindow.addEventListener("load", ensureSummaryWindowTitle, {
            once: true
        });
    }

    setTimeout(() => {
        URL.revokeObjectURL(url);
    }, 0);
}

async function loadMemberOptions() {
    try {
        const response = await fetch("members.csv");
        if (!response.ok) {
            return;
        }
        const text = await response.text();
        const rows = parseCsv(text);
        const names = new Set();

        rows.forEach((row, index) => {
            if (!row || row.length === 0) {
                return;
            }
            const rawName = (row[0] || "").trim().replace(/^"(.+)"$/, "$1");
            if (!rawName) {
                return;
            }
            if (index === 0 && /^(name|names)$/i.test(rawName)) {
                return;
            }
            names.add(rawName);
        });

        memberNames = Array.from(names).sort((a, b) => a.localeCompare(b));

        nameDatalist.innerHTML = "";
        tripLeaderDatalist.innerHTML = "";
        memberNames.forEach((name) => {
            const option = document.createElement("option");
            option.value = name;
            option.textContent = name;
            tripLeaderDatalist.appendChild(option);
            nameDatalist.appendChild(option.cloneNode(true));
        });

        document
            .querySelectorAll(".name-select")
            .forEach((select) => populateNameSelect(select));

        renderTable();
    } catch (error) {
        console.warn("Could not load member list", error);
    }
}

function formatCurrency(value) {
    if (!Number.isFinite(value)) return "";
    const fixed = Number(value).toFixed(2);
    return fixed === "-0.00" ? "0.00" : fixed;
}

function parseCsv(text) {
    const rows = [];
    let currentRow = [];
    let currentValue = "";
    let inQuotes = false;

    for (let i = 0; i < text.length; i += 1) {
        const char = text[i];

        if (inQuotes) {
            if (char === '"') {
                if (text[i + 1] === '"') {
                    currentValue += '"';
                    i += 1;
                } else {
                    inQuotes = false;
                }
            } else {
                currentValue += char;
            }
        } else if (char === '"') {
            inQuotes = true;
        } else if (char === ",") {
            currentRow.push(currentValue);
            currentValue = "";
        } else if (char === "\n") {
            currentRow.push(currentValue);
            rows.push(currentRow);
            currentRow = [];
            currentValue = "";
        } else if (char !== "\r") {
            currentValue += char;
        }
    }

    currentRow.push(currentValue);
    rows.push(currentRow);

    return rows.filter((row) => row.some((value) => value && value.trim() !== ""));
}

function syncExpenseToggleStates() {
    document
        .querySelectorAll('.expense-toggle-group input[type="checkbox"]')
        .forEach((checkbox) => {
            const key = checkbox.dataset.expenseKey;
            const expense = baseExpenses.find((item) => item.key === key);
            if (expense) {
                checkbox.checked = expense.enabled;
            }
        });
}

function getDateLocationTag() {
    const fallbackDate = new Date();
    const dateString = tripDateInput?.value && /^\d{4}-\d{2}-\d{2}$/.test(tripDateInput.value)
        ? tripDateInput.value
        : fallbackDate.toISOString().slice(0, 10);
    const formattedDate = dateString.replace(/-/g, "_");

    const rawLocation = tripLocationInput?.value ? tripLocationInput.value.trim() : "";
    const sanitizedLocation = rawLocation
        .replace(/[^A-Za-z0-9]+/g, "_")
        .replace(/^_+|_+$/g, "");
    const locationPart = sanitizedLocation || "Unknown";

    return `${formattedDate}_${locationPart}`;
}

function getFileBaseName(extension) {
    const tag = getDateLocationTag();
    return `${tag}.${extension}`;
}

function buildApplicationState() {
    const snapshot = {
        trip: {
            date: tripDateInput ? tripDateInput.value : "",
            location: tripLocationInput ? tripLocationInput.value : "",
            leader: tripLeaderInput ? tripLeaderInput.value : "",
            clerk: clerkInput ? clerkInput.value : ""
        },
        baseExpenseRates: { ...baseExpenseRates },
        baseExpenses: baseExpenses.map((expense) => ({
            key: expense.key,
            name: expense.name,
            enabled: expense.enabled,
            amounts: [...expense.amounts],
            consumers: [...expense.consumers]
        })),
        customExpenses: customExpenses.map((expense) => ({
            name: expense.name,
            enabled: expense.enabled,
            amounts: [...expense.amounts],
            consumers: [...expense.consumers]
        })),
        participants: participants.map((participant) => ({
            name: participant.name,
            bold: participant.bold,
            notes: participant.notes
        })),
        sharedGearAllSelected: Boolean(
            sharedGearMasterToggle && sharedGearMasterToggle.checked
        )
    };

    return snapshot;
}

function downloadAttendanceJson() {
    const state = buildApplicationState();
    const jsonContent = JSON.stringify(state, null, 2);
    const blob = new Blob([jsonContent], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = getFileBaseName("json");
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
}

function applyExpenseSnapshot(expense, snapshotEntry) {
    const participantCount = participants.length;
    const amounts = Array.isArray(snapshotEntry?.amounts)
        ? snapshotEntry.amounts
        : [];
    const consumers = Array.isArray(snapshotEntry?.consumers)
        ? snapshotEntry.consumers
        : [];

    if (snapshotEntry && typeof snapshotEntry.enabled === "boolean") {
        expense.enabled = snapshotEntry.enabled;
    }

    if (isBaseRateControlled(expense)) {
        applyBaseExpenseRateToExpense(expense.key);
    } else {
        expense.amounts = Array.from({ length: participantCount }, (_, index) =>
            index < amounts.length ? amounts[index] : ""
        );
    }

    expense.consumers = Array.from({ length: participantCount }, (_, index) => {
        if (index < consumers.length) {
            return Boolean(consumers[index]);
        }
        return Object.prototype.hasOwnProperty.call(expense, "defaultConsumerState")
            ? expense.defaultConsumerState
            : true;
    });
}

function applyApplicationState(state) {
    if (!state || typeof state !== "object") {
        window.alert("Invalid JSON data.");
        return;
    }

    const { trip, participants: participantData, baseExpenses: baseData, customExpenses: customData, baseExpenseRates: rateData, sharedGearAllSelected } = state;

    if (tripDateInput) {
        tripDateInput.value = trip?.date || "";
    }
    if (tripLocationInput) {
        tripLocationInput.value = trip?.location || "";
    }
    if (tripLeaderInput) {
        tripLeaderInput.value = trip?.leader || "";
    }
    if (clerkInput) {
        clerkInput.value = trip?.clerk || "";
    }

    participants.length = 0;
    if (Array.isArray(participantData) && participantData.length > 0) {
        participantData.forEach((entry) => {
            participants.push({
                name: entry?.name || "",
                bold: Boolean(entry?.bold),
                notes: entry?.notes || ""
            });
        });
    } else {
        participants.push({ name: "", bold: false, notes: "" });
    }

    if (rateData && typeof rateData === "object") {
        Object.keys(baseExpenseRates).forEach((key) => {
            const raw = rateData[key];
            if (raw === "" || raw === null) {
                baseExpenseRates[key] = "";
                return;
            }
            const numeric = Number(raw);
            baseExpenseRates[key] = Number.isFinite(numeric) ? numeric : baseExpenseRates[key];
        });
    }

    baseExpenses.forEach((expense) => {
        const snapshotEntry = Array.isArray(baseData)
            ? baseData.find((item) => item && item.key === expense.key)
            : null;
        applyExpenseSnapshot(expense, snapshotEntry);
    });

    customExpenses.length = 0;
    customExpenseCounter = 0;
    if (Array.isArray(customData)) {
        customData.forEach((entry) => {
            const customExpense = createExpense({ name: entry?.name || "Custom Expense" });
            if (typeof entry?.enabled === "boolean") {
                customExpense.enabled = entry.enabled;
            }
            customExpense.amounts = Array.from({ length: participants.length }, (_, index) => {
                if (Array.isArray(entry?.amounts) && index < entry.amounts.length) {
                    return entry.amounts[index];
                }
                return "";
            });
            customExpense.consumers = Array.from({ length: participants.length }, (_, index) => {
                if (Array.isArray(entry?.consumers) && index < entry.consumers.length) {
                    return Boolean(entry.consumers[index]);
                }
                return customExpense.defaultConsumerState;
            });
            customExpenses.push(customExpense);
        });
    }

    syncBaseExpenseInputsFromRates();
    syncExpenseToggleStates();
    renderTable();

    if (sharedGearMasterToggle) {
        sharedGearMasterToggle.checked = Boolean(sharedGearAllSelected);
        syncSharedGearMasterToggleState();
    }

    renderBankingDetails();
}

function loadTableFromJsonContent(text) {
    try {
        const parsed = JSON.parse(text);
        applyApplicationState(parsed);
    } catch (error) {
        console.error("Could not parse JSON", error);
        window.alert("Could not load JSON. Please check the file format.");
    }
}

function ensureExpenseSize(expense) {
    const needed = participants.length;
    const rateKey = isBaseRateControlled(expense) ? expense.key : null;
    const rateValue = rateKey ? baseExpenseRates[rateKey] : null;
    while (expense.amounts.length < needed) {
        if (rateKey) {
            expense.amounts.push(rateValue === "" ? "" : rateValue);
        } else {
            expense.amounts.push("");
        }
    }
    while (expense.consumers.length < needed) {
        const defaultState = Object.prototype.hasOwnProperty.call(
            expense,
            "defaultConsumerState"
        )
            ? expense.defaultConsumerState
            : true;
        expense.consumers.push(defaultState);
    }
    while (expense.amounts.length > needed) {
        expense.amounts.pop();
    }
    while (expense.consumers.length > needed) {
        expense.consumers.pop();
    }
}

function syncAllExpenseSizes() {
    getAllExpenses().forEach(ensureExpenseSize);
}

function renderTable() {
    syncAllExpenseSizes();
    const activeExpenses = getActiveExpenses();

    const headerRow = document.getElementById("attendance-header");
    headerRow.innerHTML = "";
    const nameHeader = document.createElement("th");
    nameHeader.textContent = "Name";
    headerRow.appendChild(nameHeader);

    function getExpenseHeaderLabel(expense) {
        if (!expense) {
            return "";
        }
        if (isDirectChargeExpense(expense)) {
            if (expense.key === "personal-gear") {
                return "Hired Personal Gear?";
            }
            if (expense.key === "shared-gear") {
                return "Used Shared Gear?";
            }
            return `${expense.name}?`;
        }
        return expense.name;
    }

    activeExpenses.forEach((expense) => {
        const amountHeader = document.createElement("th");
        const directCharge = isDirectChargeExpense(expense);
        amountHeader.textContent = getExpenseHeaderLabel(expense);
        amountHeader.dataset.expenseId = expense.id;
        amountHeader.dataset.directCharge = directCharge ? "true" : "false";
        headerRow.appendChild(amountHeader);

        if (!directCharge) {
            const consumeHeader = document.createElement("th");
            consumeHeader.className = "consume-header";
            consumeHeader.dataset.expenseId = expense.id;
            consumeHeader.textContent = "Inc?";
            headerRow.appendChild(consumeHeader);
        }
    });

    const breakdownHeader = document.createElement("th");
    breakdownHeader.textContent = "Fee Breakdown";
    headerRow.appendChild(breakdownHeader);

    const feeHeader = document.createElement("th");
    feeHeader.textContent = "Fee";
    headerRow.appendChild(feeHeader);

    const reimbHeader = document.createElement("th");
    reimbHeader.className = "reimburse-header";
    reimbHeader.innerHTML =
        '<span class="reimburse-label">Reimburse</span><span class="due-label">(Due)</span>';
    headerRow.appendChild(reimbHeader);

    const notesHeader = document.createElement("th");
    notesHeader.textContent = "Notes";
    headerRow.appendChild(notesHeader);

    renderBody(activeExpenses);
    renderFooter(activeExpenses);
    updateDuplicateNameWarnings();
    recalculate();
}

function renderBody(activeExpenses) {
    const tbody = document.getElementById("attendance-body");
    tbody.innerHTML = "";

    participants.forEach((participant, personIndex) => {
        const row = document.createElement("tr");

        const nameCell = document.createElement("td");
        const nameWrapper = document.createElement("div");
        nameWrapper.className = "name-input-wrapper";

        const nameInput = document.createElement("input");
        nameInput.type = "text";
        nameInput.value = participant.name;
        nameInput.setAttribute("list", nameListId);
        nameInput.className = "name-input" + (participant.bold ? " bold" : "");
        nameInput.dataset.personIndex = String(personIndex);

        const nameSelect = document.createElement("select");
        nameSelect.className = "name-select";
        nameSelect.dataset.personIndex = String(personIndex);
        nameSelect.setAttribute("aria-label", "Select member from list");
        nameSelect.title = "Select member";
        populateNameSelect(nameSelect);

        nameInput.addEventListener("input", (event) => {
            const value = event.target.value;
            participants[personIndex].name = value;
            if (!memberNames.includes(value)) {
                nameSelect.value = "";
            }
            recalculate();
            updateDuplicateNameWarnings();
        });

        nameInput.addEventListener("keydown", (event) => {
            if (event.key !== "Tab" || event.shiftKey) {
                return;
            }
            const nextIndex = personIndex + 1;
            const nextInput = document.querySelector(
                `.name-input[data-person-index="${nextIndex}"]`
            );
            if (!nextInput) {
                return;
            }
            event.preventDefault();
            nextInput.focus();
        });

        nameSelect.addEventListener("change", (event) => {
            const value = event.target.value;
            participants[personIndex].name = value;
            nameInput.value = value;
            recalculate();
            event.target.value = "";
            updateDuplicateNameWarnings();
        });

        nameWrapper.appendChild(nameInput);
        nameWrapper.appendChild(nameSelect);
        nameCell.appendChild(nameWrapper);
        row.appendChild(nameCell);

        activeExpenses.forEach((expense) => {
            ensureExpenseSize(expense);
            const directCharge = isDirectChargeExpense(expense);
            const amountCell = document.createElement("td");
            if (directCharge) {
                amountCell.classList.add("consume-cell");
                const consumeInput = document.createElement("input");
                consumeInput.type = "checkbox";
                consumeInput.checked = Boolean(expense.consumers[personIndex]);
                consumeInput.dataset.expenseId = expense.id;
                consumeInput.dataset.personIndex = String(personIndex);
                consumeInput.setAttribute(
                    "aria-label",
                    `${expense.name} consumed`
                );
                consumeInput.addEventListener("change", (event) => {
                    const targetExpense = findExpenseById(event.target.dataset.expenseId);
                    if (!targetExpense) {
                        return;
                    }
                    const index = Number(event.target.dataset.personIndex);
                    targetExpense.consumers[index] = event.target.checked;
                    recalculate();
                });
                amountCell.appendChild(consumeInput);
                row.appendChild(amountCell);
                return;
            }

            const amountInput = document.createElement("input");
            amountInput.type = "number";
            amountInput.step = "0.01";
            amountInput.value = expense.amounts[personIndex] !== "" ? expense.amounts[personIndex] : "";
            amountInput.placeholder = "0.00";
            amountInput.dataset.expenseId = expense.id;
            amountInput.dataset.personIndex = String(personIndex);
            if (isBaseRateControlled(expense)) {
                const rate = baseExpenseRates[expense.key];
                amountInput.value = rate === "" ? "" : rate;
                amountInput.readOnly = true;
                amountInput.tabIndex = -1;
                amountInput.classList.add("read-only-amount");
                amountInput.setAttribute(
                    "title",
                    `${expense.name} is managed from the controls above.`
                );
                amountInput.setAttribute("aria-readonly", "true");
            }
            amountInput.addEventListener("input", (event) => {
                if (event.target.readOnly) {
                    return;
                }
                const targetExpense = findExpenseById(event.target.dataset.expenseId);
                if (!targetExpense) {
                    return;
                }
                const index = Number(event.target.dataset.personIndex);
                const value = event.target.value.trim();
                targetExpense.amounts[index] = value === "" ? "" : Number(value);
                recalculate();
            });
            amountCell.appendChild(amountInput);
            row.appendChild(amountCell);

            const consumeCell = document.createElement("td");
            consumeCell.className = "consume-cell";
            const consumeInput = document.createElement("input");
            consumeInput.type = "checkbox";
            consumeInput.checked = Boolean(expense.consumers[personIndex]);
            consumeInput.dataset.expenseId = expense.id;
            consumeInput.dataset.personIndex = String(personIndex);
            consumeInput.setAttribute(
                "aria-label",
                `${expense.name} consumed`
            );
            consumeInput.addEventListener("change", (event) => {
                const targetExpense = findExpenseById(event.target.dataset.expenseId);
                if (!targetExpense) {
                    return;
                }
                const index = Number(event.target.dataset.personIndex);
                targetExpense.consumers[index] = event.target.checked;
                recalculate();
            });
            consumeCell.appendChild(consumeInput);
            row.appendChild(consumeCell);
        });

        const breakdownCell = document.createElement("td");
        breakdownCell.className = "fee-breakdown";
        breakdownCell.dataset.personIndex = personIndex;
        row.appendChild(breakdownCell);

        const feeCell = document.createElement("td");
        feeCell.className = "fee-value";
        feeCell.dataset.personIndex = personIndex;
        row.appendChild(feeCell);

        const reimbCell = document.createElement("td");
        reimbCell.className = "reimbursed-value";
        reimbCell.dataset.personIndex = personIndex;
        row.appendChild(reimbCell);

        const notesCell = document.createElement("td");
        const notesInput = document.createElement("textarea");
        notesInput.value = participant.notes;
        notesInput.addEventListener("input", (event) => {
            participants[personIndex].notes = event.target.value;
        });
        notesCell.appendChild(notesInput);
        row.appendChild(notesCell);

        tbody.appendChild(row);
    });
}

function renderFooter(activeExpenses) {
    const tfoot = document.getElementById("attendance-foot");
    tfoot.innerHTML = "";
    const row = document.createElement("tr");
    row.className = "totals-row";

    const blankCell = document.createElement("td");
    blankCell.textContent = "";
    row.appendChild(blankCell);

    activeExpenses.forEach((expense) => {
        const totalCell = document.createElement("td");
        totalCell.className = "expense-total";
        totalCell.dataset.expenseId = expense.id;
        totalCell.textContent = "Total: $0.00";
        if (isDirectChargeExpense(expense)) {
            totalCell.dataset.directCharge = "true";
            row.appendChild(totalCell);
        } else {
            row.appendChild(totalCell);

            const consumersCell = document.createElement("td");
            consumersCell.className = "expense-consumers";
            consumersCell.dataset.expenseId = expense.id;
            consumersCell.textContent = "Consumers: 0";
            row.appendChild(consumersCell);
        }
    });

    const breakdownCell = document.createElement("td");
    breakdownCell.innerHTML = "<strong>Total</strong>";
    row.appendChild(breakdownCell);

    const feeCell = document.createElement("td");
    feeCell.className = "fee-value total-fee";
    row.appendChild(feeCell);

    const reimbCell = document.createElement("td");
    reimbCell.className = "reimbursed-value total-reimbursed";
    row.appendChild(reimbCell);

    const noteCell = document.createElement("td");
    noteCell.textContent = "";
    row.appendChild(noteCell);

    tfoot.appendChild(row);
}

function syncSharedGearMasterToggleState() {
    if (!sharedGearMasterToggle) {
        return;
    }

    const sharedGearExpense = getSharedGearExpense();
    if (!sharedGearExpense) {
        sharedGearMasterToggle.checked = false;
        sharedGearMasterToggle.indeterminate = false;
        sharedGearMasterToggle.disabled = true;
        return;
    }

    if (!sharedGearExpense.enabled) {
        sharedGearMasterToggle.checked = false;
        sharedGearMasterToggle.indeterminate = false;
        sharedGearMasterToggle.disabled = true;
        return;
    }

    sharedGearMasterToggle.disabled = false;
    ensureExpenseSize(sharedGearExpense);

    let relevantIndexes = participants
        .map((participant, index) => ({
            index,
            hasName: Boolean(participant.name && participant.name.trim())
        }))
        .filter((entry) => entry.hasName);

    if (relevantIndexes.length === 0) {
        relevantIndexes = participants.map((_, index) => ({ index }));
    }

    const total = relevantIndexes.length;
    let checkedCount = 0;
    relevantIndexes.forEach(({ index }) => {
        if (sharedGearExpense.consumers[index]) {
            checkedCount += 1;
        }
    });

    if (total === 0) {
        sharedGearMasterToggle.checked = false;
        sharedGearMasterToggle.indeterminate = false;
        return;
    }

    sharedGearMasterToggle.indeterminate =
        checkedCount > 0 && checkedCount < total;
    sharedGearMasterToggle.checked = checkedCount === total;
}

function recalculate() {
    const activeExpenses = getActiveExpenses();
    const participantFeeTotals = new Array(participants.length).fill(0);
    const participantFeeBreakdowns = participants.map(() => []);
    const participantContributions = new Array(participants.length).fill(0);
    let clubIncome = 0;

    activeExpenses.forEach((expense) => {
        ensureExpenseSize(expense);
        if (isDirectChargeExpense(expense)) {
            const rateValue = baseExpenseRates[expense.key];
            const numericRate = Number(rateValue);
            const perPersonCharge = Number.isFinite(numericRate) ? numericRate : 0;
            let total = 0;
            let consumerCount = 0;

            participants.forEach((participant, personIndex) => {
                const hasName = Boolean(participant.name && participant.name.trim());
                if (!hasName) {
                    return;
                }
                if (expense.consumers[personIndex]) {
                    consumerCount += 1;
                    const charge = perPersonCharge;
                    participantFeeTotals[personIndex] += charge;
                    if (charge > 0) {
                        participantFeeBreakdowns[personIndex].push({
                            name: expense.name,
                            value: charge
                        });
                    }
                    if (charge > 0) {
                        clubIncome += charge;
                    }
                    total += charge;
                }
            });

            const totalCell = document.querySelector(
                `.expense-total[data-expense-id="${expense.id}"]`
            );
            if (totalCell) {
                const totalText = formatCurrency(total);
                totalCell.innerHTML = `Total: $${totalText || "0.00"}`;
                const summary = document.createElement("div");
                summary.textContent = `Selected: ${consumerCount}`;
                totalCell.appendChild(summary);
            }

            const consumersCell = document.querySelector(
                `.expense-consumers[data-expense-id="${expense.id}"]`
            );
            if (consumersCell) {
                consumersCell.textContent = `Consumers: ${consumerCount}`;
            }

            return;
        }

        let total = 0;
        const consumers = [];

        expense.amounts.forEach((amount, personIndex) => {
            const participant = participants[personIndex];
            const hasName = Boolean(participant.name && participant.name.trim());
            if (hasName && amount !== "" && Number.isFinite(Number(amount))) {
                total += Number(amount);
                participantContributions[personIndex] += Number(amount);
            }
            if (hasName && expense.consumers[personIndex]) {
                consumers.push(personIndex);
            }
        });

        const consumerCount = consumers.length;
        const share = consumerCount > 0 ? total / consumerCount : 0;

        consumers.forEach((personIndex) => {
            participantFeeTotals[personIndex] += share;
            if (share > 0) {
                participantFeeBreakdowns[personIndex].push({
                    name: expense.name,
                    value: share
                });
            }
            if (expense.key === "personal-gear" || expense.key === "shared-gear") {
                clubIncome += share;
            }
        });

        const totalCell = document.querySelector(
            `.expense-total[data-expense-id="${expense.id}"]`
        );
        if (totalCell) {
            const totalText = formatCurrency(total);
            totalCell.textContent = `Total: $${totalText || "0.00"}`;
        }
        const consumersCell = document.querySelector(
            `.expense-consumers[data-expense-id="${expense.id}"]`
        );
        if (consumersCell) {
            const shareText =
                consumerCount > 0
                    ? `Share: $${formatCurrency(share) || "0.00"}`
                    : "Share: $0.00";
            consumersCell.innerHTML = `<div>Consumers: ${consumerCount}</div><div>${shareText}</div>`;
        }
    });

    let totalFees = 0;
    let totalBalance = 0;

    participants.forEach((participant, personIndex) => {
        const hasName = Boolean(participant.name && participant.name.trim());
        const fee = hasName ? participantFeeTotals[personIndex] : 0;
        const contributions = hasName ? participantContributions[personIndex] : 0;
        const balance = fee - contributions;

        if (hasName) {
            totalFees += fee;
            totalBalance += balance;
        }

        const breakdownCell = document.querySelector(
            `.fee-breakdown[data-person-index="${personIndex}"]`
        );
        const feeCell = document.querySelector(
            `.fee-value[data-person-index="${personIndex}"]`
        );
        const reimbCell = document.querySelector(
            `.reimbursed-value[data-person-index="${personIndex}"]`
        );

        if (breakdownCell) {
            if (hasName) {
                const breakdown = participantFeeBreakdowns[personIndex];
                breakdownCell.textContent = breakdown.length
                    ? breakdown
                        .map((entry) => `${entry.name}: $${formatCurrency(entry.value) || "0.00"}`)
                        .join("; ")
                    : "";
            } else {
                breakdownCell.textContent = "";
            }
        }
        if (feeCell) {
            feeCell.textContent = hasName && fee ? `$${formatCurrency(fee)}` : "";
        }
        if (reimbCell) {
            reimbCell.textContent = "";
            reimbCell.classList.remove("amount-due", "amount-credit");
            if (hasName && balance) {
                if (balance > 0) {
                    reimbCell.textContent = `($${formatCurrency(balance)})`;
                    reimbCell.classList.add("amount-due");
                } else {
                    reimbCell.textContent = `$${formatCurrency(Math.abs(balance))}`;
                    reimbCell.classList.add("amount-credit");
                }
            }
        }
    });

    const totalFeeCell = document.querySelector(".total-fee");
    if (totalFeeCell) {
        totalFeeCell.textContent = totalFees ? `$${formatCurrency(totalFees)}` : "";
    }

    const totalReimbCell = document.querySelector(".total-reimbursed");
    if (totalReimbCell) {
        totalReimbCell.textContent = "";
        totalReimbCell.classList.remove("amount-due", "amount-credit");
        if (totalBalance) {
            const prefix = document.createTextNode("Club Gear Depreciation: ");
            totalReimbCell.appendChild(prefix);
            const valueSpan = document.createElement("span");
            if (totalBalance > 0) {
                valueSpan.textContent = `($${formatCurrency(totalBalance)})`;
                valueSpan.classList.add("amount-due");
            } else {
                valueSpan.textContent = `$${formatCurrency(Math.abs(totalBalance))}`;
                valueSpan.classList.add("amount-credit");
            }
            totalReimbCell.appendChild(valueSpan);
        }
    }

    const clubIncomeCell = document.getElementById("club-income-value");
    if (clubIncomeCell) {
        clubIncomeCell.textContent = clubIncome ? `$${formatCurrency(clubIncome)}` : "";
    }

    syncSharedGearMasterToggleState();
}

document.getElementById("add-expense").addEventListener("click", () => {
    const expenseName = window.prompt("Enter a name for the new expense:");
    if (!expenseName) {
        return;
    }
    const trimmed = expenseName.trim();
    if (!trimmed) {
        return;
    }
    customExpenses.push(createExpense({ name: trimmed }));
    renderTable();
});

document.getElementById("remove-expense").addEventListener("click", () => {
    if (customExpenses.length === 0) {
        window.alert("There are no custom expenses to remove.");
        return;
    }
    const namesList = customExpenses.map((expense) => expense.name).join(", ");
    const targetName = window.prompt(
        `Enter the name of the expense to remove:\n${namesList}`
    );
    if (!targetName) {
        return;
    }
    const trimmed = targetName.trim().toLowerCase();
    const index = customExpenses.findIndex(
        (expense) => expense.name.toLowerCase() === trimmed
    );
    if (index === -1) {
        window.alert(`Could not find an expense named "${targetName}".`);
        return;
    }
    customExpenses.splice(index, 1);
    renderTable();
});

document.getElementById("save-json").addEventListener("click", () => {
    downloadAttendanceJson();
});

const loadJsonInput = document.getElementById("load-json-input");
document.getElementById("load-json").addEventListener("click", () => {
    loadJsonInput.value = "";
    loadJsonInput.click();
});

loadJsonInput.addEventListener("change", (event) => {
    const [file] = event.target.files;
    if (!file) {
        return;
    }
    const reader = new FileReader();
    reader.onload = () => {
        try {
            const result = reader.result;
            const textContent =
                typeof result === "string" ? result : new TextDecoder().decode(result);
            loadTableFromJsonContent(textContent);
        } catch (error) {
            console.error("Could not load JSON", error);
            window.alert("Could not load JSON. Please check the file format.");
        }
    };
    reader.readAsText(file);
});

const summariseButton = document.getElementById("summarise-button");
if (summariseButton) {
    summariseButton.addEventListener("click", () => {
        downloadAndOpenSummaryHtml();
    });
}

document.getElementById("add-row").addEventListener("click", () => {
    participants.push({ name: "", bold: false, notes: "" });
    if (sharedGearMasterToggle && sharedGearMasterToggle.checked) {
        const sharedGearExpense = getSharedGearExpense();
        if (sharedGearExpense && sharedGearExpense.enabled) {
            ensureExpenseSize(sharedGearExpense);
            sharedGearExpense.consumers[participants.length - 1] = true;
        }
    }
    renderTable();
});

document.getElementById("remove-row").addEventListener("click", () => {
    if (participants.length === 0) {
        return;
    }
    const lastParticipant = participants[participants.length - 1];
    const hasName = Boolean(lastParticipant?.name && lastParticipant.name.trim());
    if (hasName && !window.confirm("Remove the last participant row?")) {
        return;
    }
    participants.pop();
    renderTable();
});

document
    .querySelectorAll('.expense-toggle-group input[type="checkbox"]')
    .forEach((checkbox) => {
        const key = checkbox.dataset.expenseKey;
        const expense = baseExpenses.find((item) => item.key === key);
        if (!expense) {
            return;
        }
        checkbox.checked = expense.enabled;
        checkbox.addEventListener("change", (event) => {
            expense.enabled = event.target.checked;
            renderTable();
        });
    });

if (sharedGearMasterToggle) {
    sharedGearMasterToggle.addEventListener("change", (event) => {
        const sharedGearExpense = getSharedGearExpense();
        if (!sharedGearExpense || !sharedGearExpense.enabled) {
            sharedGearMasterToggle.checked = false;
            sharedGearMasterToggle.indeterminate = false;
            return;
        }

        ensureExpenseSize(sharedGearExpense);
        const desired = event.target.checked;
        for (let index = 0; index < sharedGearExpense.consumers.length; index += 1) {
            sharedGearExpense.consumers[index] = desired;
        }

        document
            .querySelectorAll(
                `input[type="checkbox"][data-expense-id="${sharedGearExpense.id}"]`
            )
            .forEach((checkbox) => {
                checkbox.checked = desired;
            });

        sharedGearMasterToggle.indeterminate = false;
        recalculate();
    });
}

function renderBankingDetails() {
    const container = document.getElementById("banking-details");
    if (!container) {
        return;
    }

    const lines = [];

    if (bankingDetailsData && typeof bankingDetailsData === "object") {
        const baseLines = [
            {
                label: "Name",
                value:
                    bankingDetailsData.Name !== undefined
                        ? bankingDetailsData.Name
                        : bankingDetailsData.name
            },
            {
                label: "BSB",
                value:
                    bankingDetailsData.BSB !== undefined
                        ? bankingDetailsData.BSB
                        : bankingDetailsData.bsb
            },
            {
                label: "Account",
                value:
                    bankingDetailsData.Account !== undefined
                        ? bankingDetailsData.Account
                        : bankingDetailsData.account
            }
        ].filter((item) => {
            if (item.value === undefined || item.value === null) {
                return false;
            }
            return String(item.value).trim() !== "";
        });

        lines.push(...baseLines);
    }

    const bankingTag = getDateLocationTag();
    if (bankingTag) {
        lines.push({ label: "Tag", value: bankingTag });
    }

    container.innerHTML = "";

    if (lines.length === 0) {
        return;
    }

    lines.forEach((line) => {
        const paragraph = document.createElement("p");
        const labelSpan = document.createElement("span");
        labelSpan.classList.add("banking-label");
        labelSpan.textContent = `${line.label}:`;
        const valueSpan = document.createElement("span");
        valueSpan.textContent = String(line.value);
        paragraph.appendChild(labelSpan);
        paragraph.appendChild(valueSpan);
        container.appendChild(paragraph);
    });
}

async function loadBankingDetails() {
    try {
        const response = await fetch("banking.json");
        if (!response.ok) {
            bankingDetailsData = null;
            renderBankingDetails();
            return;
        }
        const data = await response.json();
        bankingDetailsData =
            data && typeof data === "object" ? data : null;
    } catch (error) {
        console.warn("Could not load banking details", error);
        bankingDetailsData = null;
    }

    renderBankingDetails();
}

async function loadClerk() {
    try {
        const response = await fetch("signature.txt");
        if (!response.ok) {
            return;
        }
        const text = await response.text();
        const cleaned = text.trim();
        if (clerkInput && !clerkInput.value) {
            clerkInput.value = cleaned;
        }
    } catch (error) {
        console.warn("Could not load clerk", error);
    }
}

syncBaseExpenseInputsFromRates();
loadMemberOptions();
renderTable();
renderBankingDetails();
loadBankingDetails();
loadClerk();
