var content = null
var nav = null
function window_resize() {
    var w = window.innerWidth;
    var h = window.innerHeight;
    if (h > w) {
        content.style.width = "100%";
        content.style.marginLeft = "0";
        nav.style.width = "100%";
        nav.style.marginLeft = "0";
        content.style.borderLeft = "none"
        content.style.borderRight = "none"
    }
    else {
        content.style.width = "40rem";
        nav.style.width = "40rem";
        nav.style.marginLeft = "calc(calc(100% - 40rem) / 2)"
        content.style.marginLeft = "calc(calc(100% - 40rem) / 2)"
        content.style.borderLeft = "#ffffff22 1px solid"
        content.style.borderRight = "#ffffff22 1px solid"
    }
}

function confirm_add() {
    url = document.getElementById("url_input").value
    btn = document.getElementById("confirm_add")
    info = document.getElementById("info")
    // btn.style.display = "none"

    // fetch(base + "add?url="+url)
    fetch(base + "add?url=" + url, { method: 'GET' })
        .then(response => response.text())
        .then((response) => {
            // btn.style.display = "block"
            console.log(response)
            info.innerText = response;
            alert(response)
        }
        )
    toggle_input_dialog()
}

function update(name) {
    url = 'https://twitter.com/' + name
    fetch(base + "add?url=" + url, { method: 'GET' })
        .then(response => response.text())
        .then((response) => {
            console.log(response)
            alert(response)
            meta_reload_u(name)
        }
        )
}

function meta_reload() {
    alert("Scanning, this will take a while.")
    fetch(base + "reload", { method: 'GET' })
        .then(() => {
            location.reload()
        })
}
function meta_reload_u(u) {
    alert("Scanning, this will take a while.")
    fetch(base + "reload?u=" + u, { method: 'GET' })
        .then(() => {
            location.reload()
        })
}

var dialog_on = 0
function toggle_input_dialog() {
    dialog = document.getElementById("add_dialog")
    btn = document.getElementById("add_btn")
    if (dialog_on) {
        dialog.style.display = "none"
        btn.style.transform = "rotate(0deg)"
        btn.style.backgroundColor = "rgb(29, 155, 240)"
    }
    else {
        dialog.style.display = "block"
        btn.style.transform = "rotate(45deg)"
        btn.style.backgroundColor = "rgb(250, 30, 25)"
        fetch(base + "dl_statue", { method: 'GET' })
            .then(response => response.text())
            .then((response) => {
                console.log(response)
                document.getElementById("info").innerText = "https://twitter.com/x or https://x.com/x\n" + response;
            })
    }
    dialog_on = 1 - dialog_on

}

page_select = 0
function toggle_page_select() {
    page_dialog = document.getElementById("page_select")
    indi = document.getElementsByClassName("nav_indi")[0]
    if (page_select) {
        page_dialog.style.display = "none"
        indi.style.border = "0.1rem solid #00000000"
    }
    else {
        page_dialog.style.display = "block"
        indi.style.border = "0.1rem solid #cc3232aa"
        document.getElementById("selected_item").scrollIntoView();

    }
    page_select = 1 - page_select
}


img_l = 0
function toggle_img_large() {
    console.log(img_l)
    if (img_l) {
        history.back()
        img_large_container.style.display = "none"
        document.body.style.overflow = "scroll"
    }
    else {
        window.location.hash = "#img_large"
        img_large_container.style.display = "block"
        document.body.style.overflow = "hidden"
    }
    img_l = 1 - img_l
}

function show_large(url) {
    document.getElementById("img_large").setAttribute("src", url)
    document.getElementById("download_img").setAttribute("href", url)
    toggle_img_large()
}

io = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (!entry.isIntersecting) {
            entry.target.pause()
        }
    });
});
document.querySelectorAll("video").forEach((e) => {
    io.observe(e);
})