// main js for autobom

var activeRow = null;
var viewMode = "src";

// Session-only (gone when the tab closes): raw GitHub file → ArrayBuffer + blob URL
var sourceCache = new Map();
var sourceLoads = new Map();
// Source URLs that returned an error (e.g. 404); these show the image directly.
var missingSources = new Set();
// Bumped on every part/view change so late async results don't touch the new view.
var renderToken = 0;

function filenameFromUrl(url) {
    try {
        return decodeURIComponent(new URL(url).pathname.split("/").pop() || "model");
    } catch (e) {
        return "model";
    }
}

function loadSource(url) {
    if (sourceCache.has(url)) {
        return Promise.resolve(sourceCache.get(url));
    }
    if (sourceLoads.has(url)) {
        return sourceLoads.get(url);
    }
    let pending = fetch(url).then(function (res) {
        if (!res.ok) {
            missingSources.add(url);
            throw new Error("fetch failed (" + res.status + ")");
        }
        return res.arrayBuffer();
    }).then(function (buffer) {
        let name = filenameFromUrl(url);
        let entry = {
            buffer: buffer,
            blobUrl: URL.createObjectURL(new Blob([buffer])),
            name: name
        };
        sourceCache.set(url, entry);
        sourceLoads.delete(url);
        return entry;
    }).catch(function (err) {
        sourceLoads.delete(url);
        throw err;
    });
    sourceLoads.set(url, pending);
    return pending;
}

// Resolves true if the file is reachable, false on 404 / network error.
function sourceExists(url) {
    if (sourceCache.has(url)) return Promise.resolve(true);
    if (missingSources.has(url)) return Promise.resolve(false);
    return fetch(url, { method: "HEAD" }).then(function (res) {
        if (!res.ok) missingSources.add(url);
        return res.ok;
    }).catch(function () {
        missingSources.add(url);
        return false;
    });
}

function fallBackToImage(render, imgpath) {
    showImage(render, imgpath);
    setToolbar(false, "img");
}

function showImage(render, imgpath) {
    if (imgpath) {
        render.innerHTML = "<img class='preview-img' src='" + imgpath + "' alt='preview' />";
    } else {
        render.innerHTML = "<p class='empty-preview'>No preview</p>";
    }
}

function finishSrcLoad(render) {
    let toast = render.querySelector(".src-loading-toast");
    let placeholder = render.querySelector(".src-placeholder");
    if (toast) toast.remove();
    if (placeholder) placeholder.remove();
}

function showSrcLoading(render, imgpath, viewerHtml) {
    let img = imgpath
        ? "<img class='src-placeholder' src='" + imgpath + "' alt='preview' />"
        : "";
    render.innerHTML =
        "<div class='src-loading-toast'>Loading source...</div>" +
        img +
        "<div class='src-viewer'>" + viewerHtml + "</div>";
}

function setToolbar(canToggle, mode) {
    let toolbar = document.getElementById("render-toolbar");
    let srcBtn = document.getElementById("view-src");
    let imgBtn = document.getElementById("view-img");
    if (!toolbar) return;
    toolbar.hidden = !canToggle;
    if (srcBtn) srcBtn.classList.toggle("active", mode === "src");
    if (imgBtn) imgBtn.classList.toggle("active", mode === "img");
}

// No timeouts: a missing file falls back to the image, but a file that exists
// keeps the preview image + "Loading source..." up for as long as the render takes.
function start3dViewer(render, imgpath, url, token) {
    showSrcLoading(render, imgpath, "<div id='o3dv-host' style='width:100%;height:100%'></div>");
    loadSource(url).then(function (entry) {
        if (token !== renderToken) return;
        let host = render.querySelector("#o3dv-host");
        if (!host) return;
        if (typeof OV.EmbeddedViewer === "function") {
            host.innerHTML = "";
            let viewer = new OV.EmbeddedViewer(host, {
                backgroundColor: new OV.RGBAColor(255, 255, 255, 255),
                onModelLoaded: function () {
                    if (token === renderToken) finishSrcLoad(render);
                }
            });
            viewer.LoadModelFromFileList([new File([entry.buffer], entry.name)]);
        } else {
            host.className = "online_3d_viewer";
            host.setAttribute("backgroundcolor", "255,255,255");
            host.setAttribute("model", entry.blobUrl);
            OV.SetExternalLibLocation("web/o3dv/libs");
            OV.Init3DViewerElements();
            finishSrcLoad(render);
        }
    }).catch(function () {
        if (token === renderToken) fallBackToImage(render, imgpath);
    });
}

function startKicanvas(render, imgpath, url, token) {
    showSrcLoading(render, imgpath, "");
    sourceExists(url).then(function (exists) {
        if (token !== renderToken) return;
        if (!exists) {
            fallBackToImage(render, imgpath);
            return;
        }
        // KiCanvas picks file type from the URL path; blob: UUIDs have no .kicad_pcb suffix.
        let viewer = render.querySelector(".src-viewer");
        if (!viewer) return;
        viewer.innerHTML =
            "<kicanvas-embed style='height:100%;' src=\"" + url + "\" controls=\"full\"></kicanvas-embed>";
        let embed = viewer.querySelector("kicanvas-embed");
        if (!embed) return;
        let done = false;
        let complete = function (ok) {
            if (done || token !== renderToken) return;
            done = true;
            if (ok) {
                finishSrcLoad(render);
            } else {
                fallBackToImage(render, imgpath);
            }
        };
        embed.addEventListener("error", function () { complete(false); });
        let obs = new MutationObserver(function () {
            if (embed.loaded || embed.hasAttribute("loaded")) {
                obs.disconnect();
                complete(true);
            }
        });
        obs.observe(embed, { attributes: true });
    });
}

function showPart(row, mode) {
    let render = document.getElementById("replace-with-render");
    let type = row.getAttribute("renderpreference");
    let threedpath = row.getAttribute("3dpath");
    let kipath = row.getAttribute("kipath");
    let imgpath = row.getAttribute("imgpath");
    let srcUrl = type === "3d" ? threedpath : (type === "kicanvas" ? kipath : "");
    let srcAvailable = !!srcUrl && !missingSources.has(srcUrl);
    let offline = (typeof navigator !== "undefined" && navigator.onLine === false);
    let token = ++renderToken;

    viewMode = mode;
    setToolbar(srcAvailable, srcAvailable ? mode : "img");

    if (!srcAvailable || mode === "img" || (offline && !sourceCache.has(srcUrl))) {
        showImage(render, imgpath);
        if (srcAvailable && offline) {
            setToolbar(true, "img");
        }
        return;
    }

    if (type === "3d") {
        start3dViewer(render, imgpath, threedpath, token);
        return;
    }
    startKicanvas(render, imgpath, kipath, token);
}

function updateRender(clickedElement) {
    if (!clickedElement.hasAttribute("renderpreference")) {
        return;
    }

    if (activeRow !== null) {
        activeRow.classList.remove("active");
    }
    activeRow = clickedElement;
    clickedElement.classList.add("active");

    let type = clickedElement.getAttribute("renderpreference");
    let startMode = (type === "3d" || type === "kicanvas") ? "src" : "img";
    showPart(clickedElement, startMode);
}

function initSplitter() {
    let bulk = document.getElementById("bulk");
    let splitter = document.getElementById("splitter");
    let pane = document.getElementById("render");
    if (!bulk || !splitter || !pane) return;

    let dragging = false;
    let minList = 200;
    let minRender = 240;

    function setRenderWidth(px) {
        let rect = bulk.getBoundingClientRect();
        let maxRender = rect.width - minList - splitter.offsetWidth;
        px = Math.max(minRender, Math.min(maxRender, px));
        pane.style.flex = "0 0 " + px + "px";
        pane.style.width = px + "px";
    }

    splitter.addEventListener("pointerdown", function (e) {
        e.preventDefault();
        dragging = true;
        splitter.setPointerCapture(e.pointerId);
        document.body.classList.add("resizing");
    });
    splitter.addEventListener("pointermove", function (e) {
        if (!dragging) return;
        setRenderWidth(bulk.getBoundingClientRect().right - e.clientX);
    });
    function stopDrag() {
        if (!dragging) return;
        dragging = false;
        document.body.classList.remove("resizing");
        window.dispatchEvent(new Event("resize"));
    }
    splitter.addEventListener("pointerup", stopDrag);
    splitter.addEventListener("pointercancel", stopDrag);
}

document.addEventListener("DOMContentLoaded", function () {
    initSplitter();
    let srcBtn = document.getElementById("view-src");
    let imgBtn = document.getElementById("view-img");
    if (srcBtn) {
        srcBtn.addEventListener("click", function (e) {
            e.stopPropagation();
            if (activeRow) showPart(activeRow, "src");
        });
    }
    if (imgBtn) {
        imgBtn.addEventListener("click", function (e) {
            e.stopPropagation();
            if (activeRow) showPart(activeRow, "img");
        });
    }
});
