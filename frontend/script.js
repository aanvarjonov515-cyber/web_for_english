/* =========================================================
   ENGLISH VOCABULARY TRAINER
   Frontend Application Logic
   Version 1.1.0
========================================================= */

"use strict";

/* =========================================================
   01. GLOBAL STATE
========================================================= */

const AppState = {
    currentPage: "dashboard",

    words: [],

    filteredWords: [],

    statistics: {
        total_words: 0,
        total_attempts: 0,
        correct_attempts: 0,
        incorrect_attempts: 0,
        accuracy: 0,

        reading_attempts: 0,
        pronunciation_attempts: 0,
        writing_attempts: 0,
        listening_attempts: 0,

        strong_words: 0,
        weak_words: 0,
        due_words: 0,
    },

    study: {
        readingIndex: 0,
        pronunciationIndex: 0,
        writingIndex: 0,
        listeningIndex: 0,
    },

    settings: {
        autoPronunciation: true,
        instantFeedback: true,
        soundEffects: true,
    },

    audio: {
        player: null,
        currentUrl: "",
        currentText: "",
        rate: 1,
        playing: false,
        generating: false,
    },

    ui: {
        loading: false,
        toastTimer: null,
        celebrationTimer: null,
    },

    lastImport: [],
};


/* =========================================================
   02. DOM HELPERS
========================================================= */

function $(selector) {
    return document.querySelector(selector);
}

function $$(selector) {
    return Array.from(
        document.querySelectorAll(selector)
    );
}


/* =========================================================
   03. START APPLICATION
========================================================= */

document.addEventListener(
    "DOMContentLoaded",
    initApp
);

async function initApp() {
    loadSettings();

    bindNavigation();
    bindGlobalButtons();
    bindImportEvents();
    bindVocabularyEvents();
    bindStudyEvents();
    bindSettingsEvents();

    updateInputWordCount();
    updatePageTitle();

    createAudioPlayer();

    await loadInitialData();
}


/* =========================================================
   04. AUDIO PLAYER
========================================================= */

function createAudioPlayer() {
    if (AppState.audio.player) {
        return;
    }

    const player = new Audio();

    player.preload = "auto";

    player.addEventListener(
        "play",
        () => {
            AppState.audio.playing = true;
            updateAudioUI(true);
        }
    );

    player.addEventListener(
        "pause",
        () => {
            AppState.audio.playing = false;
            updateAudioUI(false);
        }
    );

    player.addEventListener(
        "ended",
        () => {
            AppState.audio.playing = false;
            updateAudioUI(false);
        }
    );

    player.addEventListener(
        "error",
        () => {
            AppState.audio.playing = false;
            updateAudioUI(false);
        }
    );

    AppState.audio.player = player;
}


async function playAudio(
    text,
    rate = 1
) {
    if (!text) {
        return;
    }

    const player =
        AppState.audio.player;

    if (!player) {
        createAudioPlayer();
    }

    const audio =
        AppState.audio.player;

    const cleanText =
        String(text).trim();

    if (!cleanText) {
        return;
    }

    const normalizedRate =
        Number(rate) || 1;

    const audioUrl =
        buildAudioUrl(
            cleanText,
            normalizedRate
        );

    AppState.audio.rate =
        normalizedRate;

    AppState.audio.currentText =
        cleanText;

    /* ---------------------------------------------
       If the same audio is already loaded,
       reuse it instead of requesting again.
    --------------------------------------------- */

    if (
        AppState.audio.currentUrl !== audioUrl
    ) {
        audio.src = audioUrl;
        AppState.audio.currentUrl =
            audioUrl;
    }

    try {
        audio.playbackRate =
            normalizedRate;

        await audio.play();

    } catch (error) {
        console.error(
            "Audio playback error:",
            error
        );

        showToast(
            "Audio error",
            "The pronunciation audio could not be played.",
            "error"
        );
    }
}


function buildAudioUrl(
    text,
    rate = 1
) {
    const params =
        new URLSearchParams();

    params.set(
        "text",
        text
    );

    params.set(
        "voice",
        "en-US-AriaNeural"
    );

    if (rate <= 0.75) {
        params.set(
            "rate",
            "-25%"
        );
    } else if (rate <= 0.9) {
        params.set(
            "rate",
            "-10%"
        );
    } else if (rate >= 1.15) {
        params.set(
            "rate",
            "+15%"
        );
    } else {
        params.set(
            "rate",
            "+0%"
        );
    }

    params.set(
        "pitch",
        "+0Hz"
    );

    return `/api/audio?${params.toString()}`;
}


function stopAudio() {
    const audio =
        AppState.audio.player;

    if (!audio) {
        return;
    }

    audio.pause();

    audio.currentTime = 0;

    AppState.audio.playing = false;

    updateAudioUI(false);
}


function updateAudioUI(
    isPlaying
) {
    const pronunciationButton =
        $("#pronunciationPlayButton");

    const listeningButton =
        $("#listeningPlayButton");

    if (pronunciationButton) {
        pronunciationButton.textContent =
            isPlaying
                ? "⏸"
                : "🔊";
    }

    if (listeningButton) {
        listeningButton.textContent =
            isPlaying
                ? "⏸"
                : "▶";
    }
}


/* =========================================================
   05. INITIAL DATA
========================================================= */

async function loadInitialData() {
    setLoading(
        true,
        "Loading your vocabulary...",
        "Preparing your English trainer."
    );

    try {
        await Promise.all([
            loadWords(),
            loadStatistics(),
        ]);

        renderDashboard();
        renderVocabulary();
        renderProgress();
        renderReview();

    } catch (error) {
        console.error(error);

        showToast(
            "Connection error",
            error.message,
            "error"
        );

    } finally {
        setLoading(false);
    }
}


/* =========================================================
   06. API REQUEST
========================================================= */

async function apiRequest(
    url,
    options = {}
) {
    const config = {
        ...options,
        headers: {
            "Content-Type":
                "application/json",
            ...(options.headers || {}),
        },
    };

    const response =
        await fetch(
            url,
            config
        );

    let data = null;

    try {
        data = await response.json();
    } catch {
        data = null;
    }

    if (!response.ok) {
        let message =
            "Something went wrong.";

        if (data?.detail) {
            message =
                typeof data.detail === "string"
                    ? data.detail
                    : JSON.stringify(
                        data.detail
                    );
        }

        throw new Error(message);
    }

    return data;
}


/* =========================================================
   07. WORDS
========================================================= */

async function loadWords() {
    const words =
        await apiRequest(
            "/api/words"
        );

    AppState.words =
        Array.isArray(words)
            ? words
            : [];

    AppState.filteredWords =
        [...AppState.words];

    resetStudyIndexes();

    renderDashboard();
    renderVocabulary();
    initializeStudyModes();
}


async function loadStatistics() {
    const statistics =
        await apiRequest(
            "/api/statistics"
        );

    AppState.statistics = {
        ...AppState.statistics,
        ...statistics,
    };

    renderStatistics();
    renderProgress();
}


/* =========================================================
   08. NAVIGATION
========================================================= */

function bindNavigation() {
    $$(".nav-item").forEach(
        (button) => {
            button.addEventListener(
                "click",
                () => {
                    navigateTo(
                        button.dataset.page
                    );
                }
            );
        }
    );

    $$("[data-page-target]")
        .forEach(
            (element) => {
                element.addEventListener(
                    "click",
                    () => {
                        navigateTo(
                            element.dataset.pageTarget
                        );
                    }
                );
            }
        );
}


function bindDynamicNavigation() {
    $$("[data-page-target]")
        .forEach(
            (element) => {
                if (
                    element.dataset.bound ===
                    "true"
                ) {
                    return;
                }

                element.dataset.bound =
                    "true";

                element.addEventListener(
                    "click",
                    () => {
                        navigateTo(
                            element.dataset.pageTarget
                        );
                    }
                );
            }
        );
}


function navigateTo(page) {
    if (!page) {
        return;
    }

    const targetSection =
        $(
            `[data-page-section="${page}"]`
        );

    if (!targetSection) {
        return;
    }

    $$("[data-page-section]")
        .forEach(
            (section) => {
                section.classList.toggle(
                    "active",
                    section.dataset.pageSection ===
                        page
                );
            }
        );

    $$(".nav-item")
        .forEach(
            (button) => {
                button.classList.toggle(
                    "active",
                    button.dataset.page ===
                        page
                );
            }
        );

    AppState.currentPage =
        page;

    updatePageTitle();

    switch (page) {
        case "reading":
            prepareReading();
            break;

        case "pronunciation":
            preparePronunciation();
            break;

        case "writing":
            prepareWriting();
            break;

        case "listening":
            prepareListening();
            break;

        case "review":
            renderReview();
            break;

        case "progress":
            renderProgress();
            break;

        default:
            break;
    }

    if (
        page !== "pronunciation" &&
        page !== "listening"
    ) {
        stopAudio();
    }

    closeSidebar();
}


function updatePageTitle() {
    const titles = {
        dashboard: "Dashboard",
        import: "Add Vocabulary",
        vocabulary: "My Vocabulary",
        reading: "Reading",
        pronunciation: "Pronunciation",
        writing: "Writing",
        listening: "Listening",
        review: "Review",
        progress: "My Progress",
        settings: "Settings",
    };

    setText(
        "#pageTitle",
        titles[
            AppState.currentPage
        ] || "Dashboard"
    );
}


/* =========================================================
   09. SIDEBAR
========================================================= */

function bindGlobalButtons() {
    $("#mobileMenuButton")
        ?.addEventListener(
            "click",
            openSidebar
        );

    $("#sidebarClose")
        ?.addEventListener(
            "click",
            closeSidebar
        );

    $("#refreshButton")
        ?.addEventListener(
            "click",
            refreshApplication
        );

    $("#toastClose")
        ?.addEventListener(
            "click",
            hideToast
        );

    $("#heroAudioButton")
        ?.addEventListener(
            "click",
            () => {
                playAudio(
                    "hello"
                );
            }
        );
}


async function refreshApplication() {
    setLoading(
        true,
        "Refreshing...",
        "Updating your vocabulary and progress."
    );

    try {
        await loadInitialData();

        showToast(
            "Updated",
            "Your learning data is up to date.",
            "success"
        );

    } catch (error) {
        console.error(error);

        showToast(
            "Refresh failed",
            error.message,
            "error"
        );

    } finally {
        setLoading(false);
    }
}


function openSidebar() {
    $("#sidebar")
        ?.classList.add(
            "open"
        );
}


function closeSidebar() {
    $("#sidebar")
        ?.classList.remove(
            "open"
        );
}


/* =========================================================
   10. IMPORT
========================================================= */

function bindImportEvents() {
    $("#vocabularyInput")
        ?.addEventListener(
            "input",
            updateInputWordCount
        );

    $("#importWordsButton")
        ?.addEventListener(
            "click",
            importVocabulary
        );

    $("#clearInputButton")
        ?.addEventListener(
            "click",
            clearVocabularyInput
        );
}


function updateInputWordCount() {
    const input =
        $("#vocabularyInput");

    const counter =
        $("#inputWordCount");

    if (!input || !counter) {
        return;
    }

    const text =
        input.value.trim();

    if (!text) {
        counter.textContent =
            "0 words detected";

        return;
    }

    const count =
        estimateVocabularyCount(
            text
        );

    counter.textContent =
        `${count} word${count === 1 ? "" : "s"} detected`;
}


function estimateVocabularyCount(
    text
) {
    const matches =
        text.match(
            /\/[^/\n]+\/+/g
        );

    if (matches?.length) {
        return matches.length;
    }

    return text
        .split(/\r?\n/)
        .map(
            (line) =>
                line.trim()
        )
        .filter(Boolean)
        .length;
}


async function importVocabulary() {
    const input =
        $("#vocabularyInput");

    if (!input) {
        return;
    }

    const rawText =
        input.value.trim();

    if (!rawText) {
        showToast(
            "Nothing to import",
            "Paste your English vocabulary first.",
            "warning"
        );

        input.focus();

        return;
    }

    setLoading(
        true,
        "Translating vocabulary...",
        "Processing and saving your English words."
    );

    try {
        const result =
            await apiRequest(
                "/api/import",
                {
                    method: "POST",

                    body: JSON.stringify({
                        text: rawText,
                    }),
                }
            );

        AppState.lastImport =
            result.imported || [];

        renderImportPreview(
            AppState.lastImport
        );

        input.value = "";

        updateInputWordCount();

        await loadWords();
        await loadStatistics();

        showToast(
            "Vocabulary added",
            `${result.count} word${result.count === 1 ? "" : "s"} added successfully.`,
            "success"
        );

        navigateTo(
            "import"
        );

    } catch (error) {
        console.error(error);

        showToast(
            "Import failed",
            error.message,
            "error"
        );

    } finally {
        setLoading(false);
    }
}


function clearVocabularyInput() {
    const input =
        $("#vocabularyInput");

    if (!input) {
        return;
    }

    input.value = "";

    updateInputWordCount();

    hideElement(
        "#importPreviewSection"
    );
}


/* =========================================================
   11. IMPORT PREVIEW
========================================================= */

function renderImportPreview(
    words
) {
    const section =
        $("#importPreviewSection");

    const container =
        $("#importPreviewContainer");

    const badge =
        $("#importSuccessBadge");

    if (!section || !container) {
        return;
    }

    if (!words.length) {
        hideElement(section);
        return;
    }

    showElement(section);

    if (badge) {
        badge.textContent =
            `${words.length} imported`;
    }

    const rows =
        words.map(
            (word, index) => `
                <tr>
                    <td>${index + 1}</td>

                    <td>
                        <strong>
                            ${escapeHtml(
                                word.english
                            )}
                        </strong>
                    </td>

                    <td>
                        ${escapeHtml(
                            word.pronunciation ||
                            "—"
                        )}
                    </td>

                    <td>
                        ${escapeHtml(
                            word.part_of_speech ||
                            "—"
                        )}
                    </td>

                    <td>
                        ${escapeHtml(
                            word.translation ||
                            "—"
                        )}
                    </td>
                </tr>
            `
        )
        .join("");

    container.innerHTML = `
        <table class="preview-table">

            <thead>
                <tr>
                    <th>#</th>
                    <th>English</th>
                    <th>Pronunciation</th>
                    <th>Type</th>
                    <th>O‘zbekcha</th>
                </tr>
            </thead>

            <tbody>
                ${rows}
            </tbody>

        </table>
    `;
}


/* =========================================================
   12. DASHBOARD
========================================================= */

function renderDashboard() {
    renderStatistics();
    renderRecentWords();
    updateStreak();
    updateDailyGoal();
}


function renderStatistics() {
    const stats =
        AppState.statistics;

    setText(
        "#totalWords",
        stats.total_words
    );

    setText(
        "#correctAnswers",
        stats.correct_attempts
    );

    setText(
        "#accuracy",
        `${Number(
            stats.accuracy || 0
        )}%`
    );

    setText(
        "#totalAttempts",
        stats.total_attempts
    );
}


function renderRecentWords() {
    const container =
        $("#recentWordsContainer");

    if (!container) {
        return;
    }

    const recent =
        [...AppState.words]
            .slice(-5)
            .reverse();

    if (!recent.length) {
        container.innerHTML = `
            <div class="empty-state">

                <div class="empty-state-icon">
                    📚
                </div>

                <h4>
                    No vocabulary yet
                </h4>

                <p>
                    Add your first list of English
                    words to start learning.
                </p>

                <button
                    type="button"
                    class="primary-button small"
                    data-page-target="import"
                >
                    Add first words
                </button>

            </div>
        `;

        bindDynamicNavigation();

        return;
    }

    container.innerHTML =
        recent
            .map(
                (word) => `
                    <div
                        class="word-list-card"
                        data-word-id="${word.id}"
                    >

                        <div class="word-list-main">

                            <strong>
                                ${escapeHtml(
                                    word.english
                                )}
                            </strong>

                            <small>
                                ${escapeHtml(
                                    word.part_of_speech ||
                                    ""
                                )}
                            </small>

                        </div>

                        <div class="word-list-pronunciation">
                            ${escapeHtml(
                                word.pronunciation ||
                                "—"
                            )}
                        </div>

                        <div class="word-list-translation">
                            ${escapeHtml(
                                word.translation ||
                                "—"
                            )}
                        </div>

                        <div class="word-list-actions">

                            <button
                                type="button"
                                class="small-action"
                                title="Listen"
                                data-speak-word="${escapeAttribute(
                                    word.english
                                )}"
                            >
                                🔊
                            </button>

                        </div>

                    </div>
                `
            )
            .join("");

    bindSpeechButtons(
        container
    );
}


function updateStreak() {
    const attempts =
        Number(
            AppState.statistics
                .total_attempts || 0
        );

    const streak =
        attempts > 0
            ? Math.max(
                1,
                Number(
                    AppState.statistics
                        .current_streak || 1
                )
            )
            : 0;

    setText(
        "#streakValue",
        streak
    );

    setText(
        "#progressStreak",
        `${streak} day${streak === 1 ? "" : "s"}`
    );
}


function updateDailyGoal() {
    const attempts =
        Number(
            AppState.statistics
                .total_attempts || 0
        );

    const dailyGoal = 20;

    const percentage =
        Math.min(
            100,
            Math.round(
                (attempts / dailyGoal) * 100
            )
        );

    setText(
        "#dailyGoalPercent",
        `${percentage}%`
    );

    const progress =
        $("#dailyGoalProgress");

    if (progress) {
        progress.style.width =
            `${percentage}%`;
    }
}


/* =========================================================
   13. VOCABULARY LIBRARY
========================================================= */

function bindVocabularyEvents() {
    $("#wordSearchInput")
        ?.addEventListener(
            "input",
            (event) => {
                filterVocabulary(
                    event.target.value
                );
            }
        );
}


function filterVocabulary(
    query
) {
    const search =
        query
            .trim()
            .toLowerCase();

    if (!search) {
        AppState.filteredWords =
            [...AppState.words];

    } else {
        AppState.filteredWords =
            AppState.words.filter(
                (word) => {

                    const english =
                        (
                            word.english ||
                            ""
                        ).toLowerCase();

                    const translation =
                        (
                            word.translation ||
                            ""
                        ).toLowerCase();

                    return (
                        english.includes(
                            search
                        )
                        ||
                        translation.includes(
                            search
                        )
                    );
                }
            );
    }

    renderVocabulary();
}


function renderVocabulary() {
    const container =
        $("#vocabularyList");

    if (!container) {
        return;
    }

    const words =
        AppState.filteredWords;

    if (!words.length) {
        container.innerHTML = `
            <div class="empty-state">

                <div class="empty-state-icon">
                    🔎
                </div>

                <h4>
                    ${
                        AppState.words.length
                            ? "No matching words"
                            : "Your library is empty"
                    }
                </h4>

                <p>
                    ${
                        AppState.words.length
                            ? "Try another search."
                            : "Add English vocabulary to begin learning."
                    }
                </p>

            </div>
        `;

        return;
    }

    container.innerHTML =
        words
            .map(
                createWordListCard
            )
            .join("");

    bindVocabularyActions(
        container
    );
}


function createWordListCard(
    word
) {
    return `
        <article
            class="word-list-card"
            data-word-id="${word.id}"
        >

            <div class="word-list-main">

                <strong>
                    ${escapeHtml(
                        word.english
                    )}
                </strong>

                <small>
                    ${escapeHtml(
                        word.part_of_speech ||
                        "word"
                    )}
                </small>

            </div>


            <div class="word-list-pronunciation">

                ${escapeHtml(
                    word.pronunciation ||
                    "—"
                )}

            </div>


            <div class="word-list-translation">

                ${escapeHtml(
                    word.translation ||
                    "—"
                )}

            </div>


            <div class="word-list-actions">

                <button
                    type="button"
                    class="small-action"
                    title="Listen"
                    data-action="speak"
                    data-word-id="${word.id}"
                >
                    🔊
                </button>

                <button
                    type="button"
                    class="small-action delete"
                    title="Delete"
                    data-action="delete"
                    data-word-id="${word.id}"
                >
                    ×
                </button>

            </div>

        </article>
    `;
}


function bindVocabularyActions(
    container
) {
    container
        .querySelectorAll(
            "[data-action]"
        )
        .forEach(
            (button) => {

                button.addEventListener(
                    "click",
                    async () => {

                        const wordId =
                            Number(
                                button.dataset
                                    .wordId
                            );

                        const action =
                            button.dataset.action;

                        const word =
                            findWordById(
                                wordId
                            );

                        if (!word) {
                            return;
                        }

                        if (
                            action ===
                            "speak"
                        ) {
                            await playAudio(
                                word.english
                            );
                        }

                        if (
                            action ===
                            "delete"
                        ) {
                            await removeWord(
                                wordId
                            );
                        }
                    }
                );
            }
        );
}


async function removeWord(
    wordId
) {
    const word =
        findWordById(
            wordId
        );

    if (!word) {
        return;
    }

    const confirmed =
        window.confirm(
            `Delete "${word.english}" from your vocabulary?`
        );

    if (!confirmed) {
        return;
    }

    try {
        await apiRequest(
            `/api/words/${wordId}`,
            {
                method: "DELETE",
            }
        );

        await loadWords();
        await loadStatistics();

        showToast(
            "Word deleted",
            `"${word.english}" was removed from your library.`,
            "success"
        );

    } catch (error) {
        console.error(error);

        showToast(
            "Delete failed",
            error.message,
            "error"
        );
    }
}


/* =========================================================
   14. SPEECH BUTTONS
========================================================= */

function bindSpeechButtons(
    container
) {
    container
        .querySelectorAll(
            "[data-speak-word]"
        )
        .forEach(
            (button) => {

                button.addEventListener(
                    "click",
                    () => {
                        playAudio(
                            button.dataset
                                .speakWord
                        );
                    }
                );
            }
        );
}


/* =========================================================
   15. STUDY EVENT BINDING
========================================================= */

function bindStudyEvents() {

    /* -----------------------------------------------------
       READING
    ----------------------------------------------------- */

    $("#readingPreviousButton")
        ?.addEventListener(
            "click",
            () => {
                moveReading(-1);
            }
        );

    $("#readingNextButton")
        ?.addEventListener(
            "click",
            () => {
                moveReading(1);
            }
        );


    /* -----------------------------------------------------
       PRONUNCIATION
    ----------------------------------------------------- */

    $("#pronunciationPlayButton")
        ?.addEventListener(
            "click",
            () => {
                playCurrentPronunciation();
            }
        );

    $("#slowAudioButton")
        ?.addEventListener(
            "click",
            () => {
                playCurrentPronunciation(
                    0.75
                );
            }
        );

    $("#normalAudioButton")
        ?.addEventListener(
            "click",
            () => {
                playCurrentPronunciation(
                    1
                );
            }
        );

    $("#repeatAudioButton")
        ?.addEventListener(
            "click",
            () => {
                playCurrentPronunciation(
                    AppState.audio.rate
                );
            }
        );

    $("#pronunciationNextButton")
        ?.addEventListener(
            "click",
            () => {
                movePronunciation(1);
            }
        );


    /* -----------------------------------------------------
       WRITING
    ----------------------------------------------------- */

    $("#writingSubmitButton")
        ?.addEventListener(
            "click",
            submitWritingAnswer
        );

    $("#writingNextButton")
        ?.addEventListener(
            "click",
            () => {
                moveWriting(1);
            }
        );

    $("#writingAudioButton")
        ?.addEventListener(
            "click",
            () => {

                const word =
                    getCurrentWord(
                        AppState.study
                            .writingIndex
                    );

                if (word) {
                    playAudio(
                        word.english
                    );
                }
            }
        );

    $("#writingAnswerInput")
        ?.addEventListener(
            "keydown",
            (event) => {

                if (
                    event.key === "Enter"
                ) {
                    event.preventDefault();

                    submitWritingAnswer();
                }
            }
        );


    /* -----------------------------------------------------
       LISTENING
    ----------------------------------------------------- */

    $("#listeningPlayButton")
        ?.addEventListener(
            "click",
            playCurrentListening
        );

    $("#listeningReplayButton")
        ?.addEventListener(
            "click",
            playCurrentListening
        );

    $("#listeningSubmitButton")
        ?.addEventListener(
            "click",
            submitListeningAnswer
        );

    $("#listeningNextButton")
        ?.addEventListener(
            "click",
            () => {
                moveListening(1);
            }
        );

    $("#listeningAnswerInput")
        ?.addEventListener(
            "keydown",
            (event) => {

                if (
                    event.key === "Enter"
                ) {
                    event.preventDefault();

                    submitListeningAnswer();
                }
            }
        );


    /* -----------------------------------------------------
       REVIEW
    ----------------------------------------------------- */

    $("#startReviewButton")
        ?.addEventListener(
            "click",
            startReview
        );
}


/* =========================================================
   16. INITIALIZE STUDY MODES
========================================================= */

function initializeStudyModes() {
    prepareReading();
    preparePronunciation();
    prepareWriting();
    prepareListening();
    renderReview();
}


function resetStudyIndexes() {
    AppState.study.readingIndex =
        0;

    AppState.study.pronunciationIndex =
        0;

    AppState.study.writingIndex =
        0;

    AppState.study.listeningIndex =
        0;
}


/* =========================================================
   17. READING MODE
========================================================= */

function prepareReading() {
    if (!AppState.words.length) {

        setText(
            "#readingWord",
            "No words yet"
        );

        setText(
            "#readingPronunciation",
            "Add vocabulary first"
        );

        setText(
            "#readingTranslation",
            "—"
        );

        setText(
            "#readingPosition",
            "0"
        );

        setText(
            "#readingProgressText",
            "0 / 0"
        );

        updateProgressBar(
            "#readingProgressValue",
            0
        );

        return;
    }

    const word =
        getCurrentWord(
            AppState.study
                .readingIndex
        );

    if (!word) {
        return;
    }

    setText(
        "#readingWord",
        word.english
    );

    setText(
        "#readingPronunciation",
        word.pronunciation
            ? `/${word.pronunciation}/`
            : "Pronunciation unavailable"
    );

    setText(
        "#readingTranslation",
        word.translation
    );

    setText(
        "#readingPosition",
        AppState.study
            .readingIndex + 1
    );

    setStudyProgress(
        "reading",
        AppState.study
            .readingIndex
    );
}


function moveReading(
    direction
) {
    if (!AppState.words.length) {
        showNoWordsMessage();
        return;
    }

    const maxIndex =
        AppState.words.length - 1;

    AppState.study.readingIndex =
        clamp(
            AppState.study.readingIndex
                + direction,
            0,
            maxIndex
        );

    prepareReading();
}


/* =========================================================
   18. PRONUNCIATION MODE
========================================================= */

function preparePronunciation() {
    if (!AppState.words.length) {

        setText(
            "#pronunciationWord",
            "No words yet"
        );

        setText(
            "#pronunciationIPA",
            "Add vocabulary first"
        );

        setText(
            "#pronunciationMeaning",
            "—"
        );

        setText(
            "#pronunciationProgressText",
            "0 / 0"
        );

        return;
    }

    const word =
        getCurrentWord(
            AppState.study
                .pronunciationIndex
        );

    if (!word) {
        return;
    }

    setText(
        "#pronunciationWord",
        word.english
    );

    setText(
        "#pronunciationIPA",
        word.pronunciation
            ? `/${word.pronunciation}/`
            : "Pronunciation unavailable"
    );

    setText(
        "#pronunciationMeaning",
        word.translation
    );

    setStudyProgress(
        "pronunciation",
        AppState.study
            .pronunciationIndex
    );

    if (
        AppState.settings
            .autoPronunciation
        &&
        AppState.currentPage ===
            "pronunciation"
    ) {
        setTimeout(
            () => {
                playCurrentPronunciation();
            },
            250
        );
    }
}


function movePronunciation(
    direction
) {
    if (!AppState.words.length) {
        showNoWordsMessage();
        return;
    }

    stopAudio();

    const maxIndex =
        AppState.words.length - 1;

    AppState.study.pronunciationIndex =
        clamp(
            AppState.study
                .pronunciationIndex
                + direction,
            0,
            maxIndex
        );

    preparePronunciation();
}


async function playCurrentPronunciation(
    rate = AppState.audio.rate || 1
) {
    const word =
        getCurrentWord(
            AppState.study
                .pronunciationIndex
        );

    if (!word) {
        showNoWordsMessage();
        return;
    }

    await playAudio(
        word.english,
        rate
    );
}


/* =========================================================
   19. WRITING MODE
========================================================= */

function prepareWriting() {
    hideElement(
        "#writingFeedback"
    );

    hideElement(
        "#writingNextButton"
    );

    const input =
        $("#writingAnswerInput");

    if (input) {
        input.value = "";
    }

    if (!AppState.words.length) {

        setText(
            "#writingTranslation",
            "Add vocabulary first"
        );

        setText(
            "#writingPosition",
            "00"
        );

        setText(
            "#writingProgressText",
            "0 / 0"
        );

        return;
    }

    const word =
        getCurrentWord(
            AppState.study
                .writingIndex
        );

    if (!word) {
        return;
    }

    setText(
        "#writingTranslation",
        word.translation
    );

    setText(
        "#writingPosition",
        String(
            AppState.study
                .writingIndex + 1
        ).padStart(
            2,
            "0"
        )
    );

    setStudyProgress(
        "writing",
        AppState.study
            .writingIndex
    );

    input?.focus();
}


async function submitWritingAnswer() {
    const input =
        $("#writingAnswerInput");

    if (!input) {
        return;
    }

    const answer =
        input.value.trim();

    if (!answer) {
        showToast(
            "Write an answer",
            "Type the English word before checking.",
            "warning"
        );

        input.focus();

        return;
    }

    const word =
        getCurrentWord(
            AppState.study
                .writingIndex
        );

    if (!word) {
        showNoWordsMessage();
        return;
    }

    await submitStudyAnswer(
        word,
        "writing",
        answer,
        {
            feedbackSelector:
                "#writingFeedback",

            iconSelector:
                "#writingFeedbackIcon",

            titleSelector:
                "#writingFeedbackTitle",

            messageSelector:
                "#writingFeedbackMessage",

            nextButtonSelector:
                "#writingNextButton",
        }
    );
}


function moveWriting(
    direction
) {
    if (!AppState.words.length) {
        showNoWordsMessage();
        return;
    }

    const maxIndex =
        AppState.words.length - 1;

    AppState.study.writingIndex =
        clamp(
            AppState.study
                .writingIndex
                + direction,
            0,
            maxIndex
        );

    prepareWriting();
}


/* =========================================================
   20. LISTENING MODE
========================================================= */

function prepareListening() {
    stopAudio();

    hideElement(
        "#listeningFeedback"
    );

    hideElement(
        "#listeningNextButton"
    );

    const input =
        $("#listeningAnswerInput");

    if (input) {
        input.value = "";
    }

    if (!AppState.words.length) {

        setText(
            "#listeningProgressText",
            "0 / 0"
        );

        return;
    }

    setStudyProgress(
        "listening",
        AppState.study
            .listeningIndex
    );
}


async function playCurrentListening() {
    const word =
        getCurrentWord(
            AppState.study
                .listeningIndex
        );

    if (!word) {
        showNoWordsMessage();
        return;
    }

    animateListeningWave();

    await playAudio(
        word.english,
        0.92
    );
}


async function submitListeningAnswer() {
    const input =
        $("#listeningAnswerInput");

    if (!input) {
        return;
    }

    const answer =
        input.value.trim();

    if (!answer) {
        showToast(
            "Write what you heard",
            "Listen first, then type the English word.",
            "warning"
        );

        input.focus();

        return;
    }

    const word =
        getCurrentWord(
            AppState.study
                .listeningIndex
        );

    if (!word) {
        showNoWordsMessage();
        return;
    }

    await submitStudyAnswer(
        word,
        "listening",
        answer,
        {
            feedbackSelector:
                "#listeningFeedback",

            iconSelector:
                "#listeningFeedbackIcon",

            titleSelector:
                "#listeningFeedbackTitle",

            messageSelector:
                "#listeningFeedbackMessage",

            nextButtonSelector:
                "#listeningNextButton",
        }
    );
}


function moveListening(
    direction
) {
    if (!AppState.words.length) {
        showNoWordsMessage();
        return;
    }

    stopAudio();

    const maxIndex =
        AppState.words.length - 1;

    AppState.study.listeningIndex =
        clamp(
            AppState.study
                .listeningIndex
                + direction,
            0,
            maxIndex
        );

    prepareListening();
}


function animateListeningWave() {
    const wave =
        $("#listeningWave");

    if (!wave) {
        return;
    }

    wave.classList.remove(
        "is-playing"
    );

    void wave.offsetWidth;

    wave.classList.add(
        "is-playing"
    );

    setTimeout(
        () => {
            wave.classList.remove(
                "is-playing"
            );
        },
        1800
    );
}


/* =========================================================
   21. ANSWER SUBMISSION
========================================================= */

async function submitStudyAnswer(
    word,
    mode,
    answer,
    elements
) {
    try {
        const result =
            await apiRequest(
                "/api/attempt",
                {
                    method: "POST",

                    body: JSON.stringify({
                        word_id: word.id,
                        mode,
                        user_answer: answer,
                    }),
                }
            );

        renderAnswerFeedback(
            elements,
            result
        );

        if (result.correct) {

            triggerSuccessCelebration(
                result.correct_answer,
                mode
            );

        } else {

            triggerErrorEffect(
                elements.feedbackSelector
            );
        }

        await loadStatistics();

    } catch (error) {
        console.error(error);

        showToast(
            "Could not check answer",
            error.message,
            "error"
        );
    }
}


function renderAnswerFeedback(
    elements,
    result
) {
    const feedback =
        $(
            elements.feedbackSelector
        );

    if (!feedback) {
        return;
    }

    const icon =
        $(
            elements.iconSelector
        );

    const title =
        $(
            elements.titleSelector
        );

    const message =
        $(
            elements.messageSelector
        );

    const nextButton =
        $(
            elements.nextButtonSelector
        );

    feedback.classList.remove(
        "hidden",
        "success",
        "error"
    );

    feedback.classList.add(
        result.correct
            ? "success"
            : "error"
    );

    if (icon) {
        icon.textContent =
            result.correct
                ? "✓"
                : "!";
    }

    if (title) {
        title.textContent =
            result.correct
                ? "Excellent!"
                : "Not quite";
    }

    if (message) {
        message.textContent =
            result.correct
                ? result.message
                : `Correct answer: ${result.correct_answer}`;
    }

    if (nextButton) {
        nextButton.classList.remove(
            "hidden"
        );
    }
}


/* =========================================================
   22. SUCCESS / ERROR EFFECTS
========================================================= */

function triggerSuccessCelebration(
    answer,
    mode
) {
    const overlay =
        $("#celebrationOverlay");

    const title =
        $("#celebrationTitle");

    const message =
        $("#celebrationMessage");

    if (!overlay) {
        return;
    }

    clearTimeout(
        AppState.ui
            .celebrationTimer
    );

    if (title) {
        title.textContent =
            "Excellent!";
    }

    if (message) {
        message.textContent =
            `Correct ${getModeName(mode).toLowerCase()} answer!`;
    }

    overlay.classList.remove(
        "hidden"
    );

    overlay.setAttribute(
        "aria-hidden",
        "false"
    );

    if (
        AppState.settings
            .soundEffects
    ) {
        playSuccessSound();
    }

    AppState.ui.celebrationTimer =
        setTimeout(
            () => {
                overlay.classList.add(
                    "hidden"
                );

                overlay.setAttribute(
                    "aria-hidden",
                    "true"
                );
            },
            1400
        );
}


function triggerErrorEffect(
    selector
) {
    const feedback =
        $(selector);

    if (!feedback) {
        return;
    }

    feedback.animate(
        [
            {
                transform:
                    "translateX(0)",
            },
            {
                transform:
                    "translateX(-7px)",
            },
            {
                transform:
                    "translateX(7px)",
            },
            {
                transform:
                    "translateX(-5px)",
            },
            {
                transform:
                    "translateX(5px)",
            },
            {
                transform:
                    "translateX(0)",
            },
        ],
        {
            duration: 390,
            easing: "ease-out",
        }
    );

    if (
        AppState.settings
            .soundEffects
    ) {
        playErrorSound();
    }
}


/* =========================================================
   23. SOUND EFFECT ENGINE
========================================================= */

let soundContext = null;


function getAudioContext() {
    if (soundContext) {
        return soundContext;
    }

    const AudioContextClass =
        window.AudioContext ||
        window.webkitAudioContext;

    if (!AudioContextClass) {
        return null;
    }

    soundContext =
        new AudioContextClass();

    return soundContext;
}


function playTone(
    frequency,
    duration,
    type = "sine",
    volume = 0.035
) {
    const context =
        getAudioContext();

    if (!context) {
        return;
    }

    if (
        context.state ===
        "suspended"
    ) {
        context.resume();
    }

    const oscillator =
        context.createOscillator();

    const gain =
        context.createGain();

    oscillator.type =
        type;

    oscillator.frequency.value =
        frequency;

    gain.gain.setValueAtTime(
        0,
        context.currentTime
    );

    gain.gain.linearRampToValueAtTime(
        volume,
        context.currentTime + 0.015
    );

    gain.gain.exponentialRampToValueAtTime(
        0.0001,
        context.currentTime + duration
    );

    oscillator.connect(
        gain
    );

    gain.connect(
        context.destination
    );

    oscillator.start();

    oscillator.stop(
        context.currentTime +
        duration +
        0.02
    );
}


function playSuccessSound() {
    playTone(
        523.25,
        0.10,
        "sine",
        0.035
    );

    setTimeout(
        () => {
            playTone(
                659.25,
                0.12,
                "sine",
                0.035
            );
        },
        95
    );

    setTimeout(
        () => {
            playTone(
                783.99,
                0.20,
                "sine",
                0.04
            );
        },
        200
    );
}


function playErrorSound() {
    playTone(
        220,
        0.12,
        "triangle",
        0.025
    );

    setTimeout(
        () => {
            playTone(
                180,
                0.17,
                "triangle",
                0.022
            );
        },
        100
    );
}


/* =========================================================
   24. PROGRESS
========================================================= */

function setStudyProgress(
    mode,
    index
) {
    const total =
        AppState.words.length;

    if (!total) {
        return;
    }

    const current =
        Math.min(
            index + 1,
            total
        );

    const percentage =
        Math.round(
            (current / total) * 100
        );

    setText(
        `#${mode}ProgressText`,
        `${current} / ${total}`
    );

    updateProgressBar(
        `#${mode}ProgressValue`,
        percentage
    );
}


function renderProgress() {
    const stats =
        AppState.statistics;

    setText(
        "#progressAccuracy",
        `${Number(
            stats.accuracy || 0
        )}%`
    );

    setText(
        "#progressWords",
        stats.total_words || 0
    );

    setText(
        "#progressCorrect",
        stats.correct_attempts || 0
    );

    setText(
        "#progressAttempts",
        stats.total_attempts || 0
    );

    updateStreak();

    const circle =
        $(".progress-circle");

    if (circle) {
        const accuracy =
            clamp(
                Number(
                    stats.accuracy || 0
                ),
                0,
                100
            );

        const degrees =
            Math.round(
                (accuracy / 100) * 360
            );

        circle.style.background =
            `conic-gradient(
                var(--primary) 0deg,
                var(--primary) ${degrees}deg,
                #dce5ff ${degrees}deg,
                #dce5ff 360deg
            )`;
    }
}


/* =========================================================
   25. REVIEW
========================================================= */

function renderReview() {
    const stats =
        AppState.statistics;

    const totalWords =
        Number(
            stats.total_words || 0
        );

    const due =
        Number(
            stats.due_words ??
            totalWords
        );

    const strong =
        Number(
            stats.strong_words || 0
        );

    const weak =
        Number(
            stats.weak_words || 0
        );

    setText(
        "#reviewDueCount",
        due
    );

    setText(
        "#reviewStrongCount",
        strong
    );

    setText(
        "#reviewWeakCount",
        weak
    );
}


function startReview() {
    if (!AppState.words.length) {
        showToast(
            "Nothing to review",
            "Add vocabulary first.",
            "warning"
        );

        navigateTo(
            "import"
        );

        return;
    }

    AppState.study.writingIndex =
        0;

    navigateTo(
        "writing"
    );

    showToast(
        "Review started",
        "Use active recall to strengthen your vocabulary.",
        "success"
    );
}


/* =========================================================
   26. SETTINGS
========================================================= */

function bindSettingsEvents() {
    $("#autoPronunciation")
        ?.addEventListener(
            "change",
            (event) => {

                AppState.settings
                    .autoPronunciation =
                    event.target.checked;

                saveSettings();
            }
        );

    $("#instantFeedback")
        ?.addEventListener(
            "change",
            (event) => {

                AppState.settings
                    .instantFeedback =
                    event.target.checked;

                saveSettings();
            }
        );

    $("#soundEffects")
        ?.addEventListener(
            "change",
            (event) => {

                AppState.settings
                    .soundEffects =
                    event.target.checked;

                saveSettings();
            }
        );
}


function loadSettings() {
    try {
        const raw =
            localStorage.getItem(
                "english_vocab_settings"
            );

        if (!raw) {
            syncSettingsUI();
            return;
        }

        const saved =
            JSON.parse(
                raw
            );

        AppState.settings = {
            ...AppState.settings,
            ...saved,
        };

        syncSettingsUI();

    } catch (error) {
        console.warn(
            "Could not load settings:",
            error
        );

        syncSettingsUI();
    }
}


function saveSettings() {
    try {
        localStorage.setItem(
            "english_vocab_settings",
            JSON.stringify(
                AppState.settings
            )
        );

        syncSettingsUI();

    } catch (error) {
        console.warn(
            "Could not save settings:",
            error
        );
    }
}


function syncSettingsUI() {
    const auto =
        $("#autoPronunciation");

    const feedback =
        $("#instantFeedback");

    const effects =
        $("#soundEffects");

    if (auto) {
        auto.checked =
            Boolean(
                AppState.settings
                    .autoPronunciation
            );
    }

    if (feedback) {
        feedback.checked =
            Boolean(
                AppState.settings
                    .instantFeedback
            );
    }

    if (effects) {
        effects.checked =
            Boolean(
                AppState.settings
                    .soundEffects
            );
    }
}


/* =========================================================
   27. KEYBOARD SHORTCUTS
========================================================= */

document.addEventListener(
    "keydown",
    (event) => {

        const target =
            document.activeElement;

        const typing =
            target &&
            (
                target.tagName ===
                    "INPUT"
                ||
                target.tagName ===
                    "TEXTAREA"
            );

        /* Space = play audio */

        if (
            event.code ===
                "Space"
            &&
            !typing
        ) {
            event.preventDefault();

            if (
                AppState.currentPage ===
                "pronunciation"
            ) {
                playCurrentPronunciation();
            }

            if (
                AppState.currentPage ===
                "listening"
            ) {
                playCurrentListening();
            }
        }

        /* Arrow keys in reading mode */

        if (
            !typing
            &&
            AppState.currentPage ===
                "reading"
        ) {

            if (
                event.key ===
                "ArrowRight"
            ) {
                moveReading(1);
            }

            if (
                event.key ===
                "ArrowLeft"
            ) {
                moveReading(-1);
            }
        }

        /* Escape */

        if (
            event.key ===
                "Escape"
        ) {
            closeSidebar();
            hideToast();
        }
    }
);


/* =========================================================
   28. LOADING UI
========================================================= */

function setLoading(
    visible,
    title = "Processing...",
    message = "Please wait."
) {
    const overlay =
        $("#loadingOverlay");

    if (!overlay) {
        return;
    }

    AppState.ui.loading =
        Boolean(visible);

    setText(
        "#loadingTitle",
        title
    );

    setText(
        "#loadingMessage",
        message
    );

    overlay.classList.toggle(
        "hidden",
        !visible
    );
}


/* =========================================================
   29. TOAST
========================================================= */

function showToast(
    title,
    message,
    type = "success"
) {
    const toast =
        $("#toast");

    const toastTitle =
        $("#toastTitle");

    const toastMessage =
        $("#toastMessage");

    const toastIcon =
        $("#toastIcon");

    if (
        !toast ||
        !toastTitle ||
        !toastMessage
    ) {
        return;
    }

    clearTimeout(
        AppState.ui.toastTimer
    );

    toastTitle.textContent =
        title;

    toastMessage.textContent =
        message;

    if (toastIcon) {

        if (
            type === "error"
        ) {
            toastIcon.textContent =
                "!";
        } else if (
            type === "warning"
        ) {
            toastIcon.textContent =
                "!";
        } else {
            toastIcon.textContent =
                "✓";
        }
    }

    toast.classList.remove(
        "hidden"
    );

    AppState.ui.toastTimer =
        setTimeout(
            hideToast,
            4200
        );
}


function hideToast() {
    $("#toast")
        ?.classList.add(
            "hidden"
        );
}


/* =========================================================
   30. HELPERS
========================================================= */

function getCurrentWord(
    index
) {
    return (
        AppState.words[index] ||
        null
    );
}


function findWordById(
    id
) {
    return (
        AppState.words.find(
            (word) =>
                Number(
                    word.id
                ) ===
                Number(id)
        ) || null
    );
}


function setText(
    selector,
    value
) {
    const element =
        typeof selector === "string"
            ? $(selector)
            : selector;

    if (!element) {
        return;
    }

    element.textContent =
        String(
            value ?? ""
        );
}


function showElement(
    selector
) {
    const element =
        typeof selector === "string"
            ? $(selector)
            : selector;

    element?.classList.remove(
        "hidden"
    );
}


function hideElement(
    selector
) {
    const element =
        typeof selector === "string"
            ? $(selector)
            : selector;

    element?.classList.add(
        "hidden"
    );
}


function updateProgressBar(
    selector,
    percentage
) {
    const element =
        $(selector);

    if (!element) {
        return;
    }

    const value =
        clamp(
            Number(
                percentage
            ) || 0,
            0,
            100
        );

    element.style.width =
        `${value}%`;
}


function clamp(
    value,
    min,
    max
) {
    return Math.min(
        Math.max(
            Number(value),
            min
        ),
        max
    );
}


function getModeName(
    mode
) {
    const names = {
        reading: "Reading",
        pronunciation:
            "Pronunciation",
        writing: "Writing",
        listening: "Listening",
    };

    return (
        names[mode] ||
        "Learning"
    );
}


function showNoWordsMessage() {
    showToast(
        "No vocabulary",
        "Add some English words before starting a study mode.",
        "warning"
    );

    navigateTo(
        "import"
    );
}


/* =========================================================
   31. HTML SAFETY
========================================================= */

function escapeHtml(
    value
) {
    return String(
        value ?? ""
    )
        .replaceAll(
            "&",
            "&amp;"
        )
        .replaceAll(
            "<",
            "&lt;"
        )
        .replaceAll(
            ">",
            "&gt;"
        )
        .replaceAll(
            '"',
            "&quot;"
        )
        .replaceAll(
            "'",
            "&#039;"
        );
}


function escapeAttribute(
    value
) {
    return escapeHtml(
        value
    );
}


/* =========================================================
   32. GLOBAL ERROR HANDLING
========================================================= */

window.addEventListener(
    "error",
    (event) => {
        console.error(
            "Global application error:",
            event.error
        );
    }
);


window.addEventListener(
    "unhandledrejection",
    (event) => {
        console.error(
            "Unhandled promise rejection:",
            event.reason
        );
    }
);


/* =========================================================
   33. DEBUG API
========================================================= */

window.VocabLab = {
    state:
        AppState,

    reload:
        loadInitialData,

    navigate:
        navigateTo,

    playAudio:
        playAudio,

    stopAudio:
        stopAudio,

    getWords:
        () => [
            ...AppState.words
        ],

    getStatistics:
        () => ({
            ...AppState.statistics,
        }),
};