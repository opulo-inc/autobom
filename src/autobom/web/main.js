// main js for autobom

var activeRow = null;
var viewMode = "src";

// Session-only (gone when the tab closes): raw GitHub file → ArrayBuffer + blob URL
var sourceCache = new Map();
var sourceLoads = new Map();

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

function showImage(render, imgpath) {
    if (imgpath) {
        render.innerHTML = "<img src='" + imgpath + "' alt='preview' />";
    } else {
        render.innerHTML = "<p style='margin-top:45%;'>No preview</p>";
    }
}

function finishSrcLoad(render, ok) {
    let toast = render.querySelector(".src-loading-toast");
    let placeholder = render.querySelector(".src-placeholder");
    if (ok) {
        if (toast) toast.remove();
        if (placeholder) placeholder.remove();
        return;
    }
    if (toast) toast.textContent = "Could not load source";
}

function showSrcLoading(render, imgpath, viewerHtml) {
    let img = imgpath
        ? "<img class='src-placeholder' src='" + imgpath + "' alt='preview' />"
        : "";
    render.innerHTML =
        "<div class='src-loading-toast'>Loading source…</div>" +
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

function start3dViewer(render, imgpath, url) {
    showSrcLoading(render, imgpath, "<div id='o3dv-host' style='width:100%;height:100%'></div>");
    loadSource(url).then(function (entry) {
        let host = render.querySelector("#o3dv-host");
        if (!host) return;
        if (typeof OV.EmbeddedViewer === "function") {
            host.innerHTML = "";
            let viewer = new OV.EmbeddedViewer(host, {
                backgroundColor: new OV.RGBAColor(255, 255, 255, 255)
            });
            viewer.LoadModelFromFileList([new File([entry.buffer], entry.name)]);
        } else {
            host.className = "online_3d_viewer";
            host.setAttribute("backgroundcolor", "255,255,255");
            host.setAttribute("model", entry.blobUrl);
            OV.SetExternalLibLocation("web/o3dv/libs");
            OV.Init3DViewerElements();
        }
        finishSrcLoad(render, true);
    }).catch(function () {
        finishSrcLoad(render, false);
    });
}

function startKicanvas(render, imgpath, url) {
    showSrcLoading(render, imgpath, "");
    loadSource(url).then(function (entry) {
        let viewer = render.querySelector(".src-viewer");
        if (!viewer) return;
        viewer.innerHTML = "<kicanvas-embed style='height:100%;' src=\"" + entry.blobUrl + "\" controls=\"basic\"></kicanvas-embed>";
        let embed = viewer.querySelector("kicanvas-embed");
        let done = false;
        let complete = function (ok) {
            if (done) return;
            done = true;
            finishSrcLoad(render, ok);
        };
        if (embed) {
            embed.addEventListener("error", function () { complete(false); });
            let obs = new MutationObserver(function () {
                if (embed.loaded || embed.hasAttribute("loaded")) {
                    obs.disconnect();
                    complete(true);
                }
            });
            obs.observe(embed, { attributes: true });
        }
        setTimeout(function () { complete(true); }, 15000);
    }).catch(function () {
        finishSrcLoad(render, false);
    });
}

function showPart(row, mode) {
    let render = document.getElementById("replace-with-render");
    let type = row.getAttribute("renderpreference");
    let threedpath = row.getAttribute("3dpath");
    let kipath = row.getAttribute("kipath");
    let imgpath = row.getAttribute("imgpath");
    let srcAvailable = (type === "3d" && threedpath) || (type === "kicanvas" && kipath);
    let offline = (typeof navigator !== "undefined" && navigator.onLine === false);

    viewMode = mode;
    setToolbar(srcAvailable, srcAvailable ? mode : "img");

    if (!srcAvailable || mode === "img" || (offline && !sourceCache.has(type === "3d" ? threedpath : kipath))) {
        showImage(render, imgpath);
        if (srcAvailable && offline) {
            setToolbar(true, "img");
        }
        return;
    }

    if (type === "3d") {
        start3dViewer(render, imgpath, threedpath);
        return;
    }
    startKicanvas(render, imgpath, kipath);
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

document.addEventListener("DOMContentLoaded", function () {
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

onresize = (event) => {

};
