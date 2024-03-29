import { lifemap } from "lifemapjs";

import "./styles.css";

function render({ model, el }) {
    // Traitlets
    let data = () => model.get("data");
    let layers = () => model.get("layers");
    let options = () => model.get("options");
    let width = () => model.get("width");
    let height = () => model.get("height");

    // Add container div
    const container = document.createElement("div");
    container.classList.add("pylifemap-map");

    // Create map
    const map = lifemap(container, data(), layers(), options());

    container.style.height = height();
    container.style.width = width();

    el.appendChild(container);

    // Add traitlets change callback
    model.on("change:data", () => _onDataChanged(model, map));
    model.on("change:layers", () => _onLayersChanged(model, map));
    model.on("change:width", () => _onWidthChanged(model, el));
    model.on("change:height", () => _onHeightChanged(model, el));
}

// Data value change callback
function _onDataChanged(model, map) {
    let data = () => model.get("data");
    map.update_data(data());
}

// Layers value change callback
function _onLayersChanged(model, map) {
    let layers = () => model.get("layers");
    map.update_layers(layers());
}

// Width value change callback
function _onWidthChanged(model, el) {
    let width = () => model.get("width");
    let container = el.querySelector(":scope > .pylifemap-map");
    container.style.width = width();
}

// Height value change callback
function _onHeightChanged(model, el) {
    let height = () => model.get("height");
    let container = el.querySelector(":scope > .pylifemap-map");
    container.style.height = height();
}

export default { render };
