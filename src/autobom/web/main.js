// main js for autobom

var activeRow = null;

function showImage(render, imgpath) {
    if (imgpath) {
        render.innerHTML = "<img src='" + imgpath + "' alt='preview' />";
    } else {
        render.innerHTML = "<p style='margin-top:45%;'>No preview</p>";
    }
}

function updateRender(clickedElement){

    let render = document.getElementById("replace-with-render");

    if(clickedElement.hasAttribute("renderpreference")){
        let type = clickedElement.getAttribute("renderpreference");
        let threedpath = clickedElement.getAttribute("3dpath");
        let kipath = clickedElement.getAttribute("kipath");
        let imgpath = clickedElement.getAttribute("imgpath");

        if (activeRow !== null){
            activeRow.classList.remove("active");
        }

        activeRow = clickedElement;

        clickedElement.classList.add("active");

        let offline = (typeof navigator !== "undefined" && navigator.onLine === false);

        if (type == "img" || offline) {
            showImage(render, imgpath);
        }
        else if (type == "3d" && threedpath) {
            try {
                render.innerHTML = "<div class='online_3d_viewer' style='width: 100%; height: 100%;' backgroundcolor='255,255,255' model='" + threedpath + "'></div>";
                OV.SetExternalLibLocation('web/o3dv/libs');
                OV.Init3DViewerElements();
            } catch (e) {
                showImage(render, imgpath);
            }
        }
        else if (type == "kicanvas" && kipath) {
            render.innerHTML = "<kicanvas-embed style='height:100%;' src=\"" + kipath + "\" controls=\"basic\"></kicanvas-embed>";
        }
        else {
            showImage(render, imgpath);
        }

    }
    else{
        // there's no render for this part

    }
}

onresize = (event) => {

};
