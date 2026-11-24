"use strict";

// Vista «Lienzo interactivo» del grafo del lote con React Flow 12.12.1 (UMD servido desde /static/vendor).
// Solo dibuja: estados, motivos y avisos los calcula pipelineModel en dashboard.js, que también pinta el
// detalle. Así la lista nativa y el lienzo no pueden discrepar.
(() => {
  const h = React.createElement;
  const {ReactFlow, Background, Controls, Handle, Position} = window.ReactFlow;

  // > Textos de accesibilidad de React Flow en español; por defecto vienen en inglés y hablan de mover y borrar
  //   nodos, que aquí está desactivado.
  const ARIA = {
    "node.a11yDescription.default": "Intro o Espacio abre los eventos de la etapa; las flechas, Inicio y Fin recorren las etapas.",
    "node.a11yDescription.keyboardDisabled": "Intro o Espacio abre los eventos de la etapa.",
    "node.a11yDescription.ariaLiveMessage": () => "",
    "edge.a11yDescription.default": "Conexión entre etapas.",
    "controls.ariaLabel": "Controles del lienzo",
    "controls.zoomIn.ariaLabel": "Acercar",
    "controls.zoomOut.ariaLabel": "Alejar",
    "controls.fitView.ariaLabel": "Encajar el grafo",
    "controls.interactive.ariaLabel": "Activar o desactivar la interacción",
    "minimap.ariaLabel": "Minimapa",
    "handle.ariaLabel": "Conector",
  };

  // > Dos disposiciones según el ancho del lienzo: serpiente de 4 + 4 o, por debajo de 640 px, una columna.
  function mode(width) {
    return width > 0 && width < 640 ? "column" : "snake";
  }

  function place(layout, index) {
    if (layout === "column") return {position: {x: 0, y: index * 112}, input: Position.Top, output: Position.Bottom};
    const row = index < 4 ? 0 : 1;
    return {
      position: {x: (row === 0 ? index : 7 - index) * 210, y: row * 150},
      input: row === 0 ? Position.Left : index === 4 ? Position.Top : Position.Right,
      output: row === 0 ? (index === 3 ? Position.Bottom : Position.Right) : Position.Left,
    };
  }

  function StageNode({data}) {
    // > Mismas clases que los botones de la lista: los colores por estado salen de las mismas reglas CSS.
    return h("div", {className: "flow-node rf-stage", "data-state": data.state},
      h(Handle, {type: "target", position: data.input, isConnectable: false}),
      h("span", {className: "flow-step"}, String(data.index + 1)),
      h("span", {className: "flow-label"}, data.label),
      h("span", {className: "flow-state"}, data.summary),
      h(Handle, {type: "source", position: data.output, isConnectable: false}));
  }
  const nodeTypes = {stage: StageNode};

  function useWidth(ref) {
    const [width, setWidth] = React.useState(0);
    // > Oculto (vista Lista) el lienzo mide 0: se ignora, y al volver a mostrarse se mide antes de pintar,
    //   para no enseñar un fotograma con la disposición de otro ancho (a 390 px se saldría de la pantalla).
    const update = value => { if (value > 0) setWidth(Math.round(value)); };
    React.useLayoutEffect(() => update(ref.current.clientWidth));
    React.useEffect(() => {
      const observer = new ResizeObserver(entries => update(entries[0].contentRect.width));
      observer.observe(ref.current);
      return () => observer.disconnect();
    }, []);
    return width;
  }

  // > fitView solo encuadra al montar: si el ancho cambia sin cambiar de disposición, se reencuadra.
  function Refit({width}) {
    const {fitView} = window.ReactFlow.useReactFlow();
    React.useEffect(() => {
      const timer = setTimeout(() => fitView({padding: 0.12}), 150);
      return () => clearTimeout(timer);
    }, [width]);
    return null;
  }

  function Canvas({model, selected, labels, summary, edgeState, onSelect}) {
    const wrap = React.useRef(null);
    const width = useWidth(wrap);
    const layout = mode(width);
    const ids = model.nodes.map(node => node.id);
    // > Una sola parada de tabulación, como la lista: la etapa elegida (o la primera). Las flechas la mueven
    //   en el DOM sin volver a dibujar el lienzo, para que React Flow no recree nada bajo el foco.
    const roving = ids.includes(selected) ? selected : ids[0];
    // > En modo controlado React Flow toma las medidas del nodo que recibe: sin devolverle las que notifica,
    //   cada nodo nuevo (al elegir una etapa o al refrescar) queda oculto hasta volver a medirse y pierde el foco.
    const measured = React.useRef({});

    const nodes = React.useMemo(() => model.nodes.map((node, index) => {
      const spot = place(layout, index);
      const attributes = {"data-node": node.id, "data-state": node.state, "aria-controls": "ops-graph-detail",
        "aria-roledescription": "etapa", tabIndex: node.id === roving ? 0 : -1};
      if (node.id === selected) attributes["aria-current"] = "true";
      return {
        id: node.id, type: "stage", position: spot.position, selected: node.id === selected,
        measured: measured.current[node.id], draggable: false, connectable: false, deletable: false,
        ariaLabel: `${index + 1}. ${node.label}: ${labels[node.state]}`, domAttributes: attributes,
        data: {label: node.label, state: node.state, index, summary: summary(node), input: spot.input, output: spot.output},
      };
    }), [model, layout, selected]);
    const edges = React.useMemo(() => model.nodes.slice(1).map((next, index) => ({
      id: `${ids[index]}-${next.id}`, source: ids[index], target: next.id, className: `rf-edge-${edgeState(next)}`,
      type: layout === "snake" ? "smoothstep" : "straight", focusable: false, selectable: false, deletable: false,
      // > Conector decorativo, como el SVG de la lista: el orden ya lo dicen los números y las etiquetas.
      ariaLabel: null, domAttributes: {"aria-hidden": "true"},
    })), [model, layout]);

    // > Las flechas mueven el tabindex en el DOM; tras cada render se deja una sola parada, la de la etapa elegida.
    React.useEffect(() => {
      wrap.current.querySelectorAll(".react-flow__node").forEach(element => {
        element.tabIndex = element.dataset.id === roving ? 0 : -1;
      });
    });

    function onNodesChange(changes) {
      changes.forEach(change => {
        if (change.type === "dimensions" && change.dimensions) measured.current[change.id] = change.dimensions;
        if (change.type === "select" && change.selected) onSelect(change.id);
      });
    }

    // > Flechas, Inicio y Fin entre etapas (React Flow reserva las flechas para mover nodos seleccionables
    //   arrastrables, y aquí no se arrastra nada). Intro o Espacio los gestiona React Flow como selección.
    // > Escape: React Flow selecciona la etapa o la deselecciona y quita el foco; la lista no hace nada con él.
    function onKeyDownCapture(event) {
      if (event.key === "Escape" && event.target.closest?.(".react-flow__node")) event.stopPropagation();
    }

    function onKeyDown(event) {
      const current = event.target.closest?.(".react-flow__node");
      if (!current) return;
      // > Espacio no desplaza la página: React Flow ya lo captura como tecla de arrastre del lienzo (el smoke lo vigila).
      const index = ids.indexOf(current.dataset.id);
      const moves = {ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1};
      let target = null;
      if (event.key in moves) target = Math.min(ids.length - 1, Math.max(0, index + moves[event.key]));
      else if (event.key === "Home") target = 0;
      else if (event.key === "End") target = ids.length - 1;
      if (target === null) return;
      event.preventDefault();
      const elements = [...wrap.current.querySelectorAll(".react-flow__node")];
      elements.forEach(element => { element.tabIndex = element.dataset.id === ids[target] ? 0 : -1; });
      elements.find(element => element.dataset.id === ids[target])?.focus();
    }

    const narrow = layout === "column";
    return h("div", {ref: wrap, className: "rf-wrap", "data-mode": layout, onKeyDown, onKeyDownCapture},
      h(ReactFlow, {
        key: layout, nodes, edges, nodeTypes, onNodesChange, ariaLabelConfig: ARIA,
        fitView: true, fitViewOptions: {padding: 0.12}, minZoom: 0.4, maxZoom: 1.6,
        nodesDraggable: false, nodesConnectable: false, elementsSelectable: true,
        deleteKeyCode: null, selectionKeyCode: null, multiSelectionKeyCode: null,
        // > La rueda desplaza la página; en móvil el lienzo tampoco se arrastra para no atrapar el scroll.
        zoomOnScroll: false, preventScrolling: false, panOnDrag: !narrow, zoomOnPinch: !narrow,
        zoomOnDoubleClick: false, colorMode: "dark",
      },
      h(Background, {gap: 20, size: 1}),
      h(Refit, {width}),
      narrow ? null : h(Controls, {showInteractive: false, position: "top-right"})));
  }

  const roots = new WeakMap();
  window.DSIAFlowCanvas = {
    render(container, model, options) {
      let root = roots.get(container);
      if (!root) {
        root = ReactDOM.createRoot(container);
        roots.set(container, root);
      }
      root.render(h(Canvas, {model, ...options}));
    },
  };
})();
