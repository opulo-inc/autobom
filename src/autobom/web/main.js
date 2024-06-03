// main js for autobom

var activeRow = null;

function updateRender(clickedElement){

    let render = document.getElementById("replace-with-render");

    if(clickedElement.hasAttribute("rendertype")){
        let type = clickedElement.getAttribute("rendertype") 
        let path = clickedElement.getAttribute("renderpath")

        if (activeRow !== null){
            activeRow.classList.remove("active");
        }

        activeRow = clickedElement;

        clickedElement.classList.add("active");

        if(type == "3d"){
            render.innerHTML = "<div class='online_3d_viewer' style='width: 100%; height: 100%;' backgroundcolor='255,255,255' model='" + path + "'></div>";
            OV.SetExternalLibLocation('libs');
            // init all viewers on the page
            OV.Init3DViewerElements();
            // document.getElementById("viewer").style.setProperty("width", "100%");
        }
        else if (type == "kicanvas"){
            // add kicanvas embed to render object
            render.innerHTML = "<kicanvas-embed style='height:100%;' src=\"" + path + "\" controls=\"basic\"> </kicanvas-embed>"
        }
        else if (type == "img"){
            render.innerHTML = "<img src='" + path + "' />"
        }

    }
    else{
        // there's no render for this part

    }
}

onresize = (event) => {

};

// i need autobom to give me an object that for every part name with a render, the render type, and the render file path
