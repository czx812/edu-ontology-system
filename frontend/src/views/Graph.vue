<template>
  <section class="graph-page">
    <div class="toolbar">
      <div>
        <h1>本体图谱可视化</h1>
        <p>基于最近一次生成的本体 JSON 展示 Class、DatatypeProperty 与 DataElement 的对应关系。</p>
      </div>
    </div>

    <p v-if="notice" class="notice">{{ notice }}</p>
    <p v-if="error" class="error">{{ error }}</p>

    <template v-if="ontology">
      <div class="filters">
        <label>
          domain
          <select v-model="selectedDomain">
            <option value="">全部 domain</option>
            <option v-for="domain in domains" :key="domain" :value="domain">{{ domain }}</option>
          </select>
        </label>
        <label>
          code / label
          <input v-model="keyword" placeholder="搜索 code、label、name、field_name" />
        </label>
        <label class="switch">
          <input v-model="showReferences" type="checkbox" />
          <span>显示 references</span>
        </label>
        <label>
          maxNodes
          <input v-model.number="maxNodes" min="20" max="1200" step="10" type="number" />
        </label>
      </div>

      <div class="legend">
        <span><i class="class-dot"></i>Class</span>
        <span><i class="property-dot"></i>DatatypeProperty</span>
        <span><i class="data-dot"></i>DataElement</span>
        <strong>{{ graphStats.nodes }} 节点 / {{ graphStats.edges }} 边</strong>
        <span v-if="activeClassName" class="active-class">已展开：{{ activeClassName }}</span>
        <button v-if="activeClassName" class="text-btn" @click="collapseClass">收起</button>
        <span v-else class="active-class">点击蓝色 Class 节点展开属性</span>
      </div>

      <div class="graph-layout">
        <div class="chart-wrap">
          <div class="chart-scroll">
            <div ref="chartRef" class="chart"></div>
          </div>
        </div>

        <aside class="detail">
          <h2>节点详情</h2>
          <dl v-if="selectedNode">
            <template v-for="field in detailFields" :key="field.key">
              <dt>{{ field.label }}</dt>
              <dd>{{ formatValue(readPath(selectedNode.raw, field.key)) }}</dd>
            </template>
          </dl>
          <p v-else>点击图谱中的节点查看详情。</p>
        </aside>
      </div>
    </template>
  </section>
</template>

<script setup>
import * as echarts from "echarts";
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";

const chartRef = ref(null);
const ontology = ref(null);
const error = ref("");
const notice = ref("");
const selectedDomain = ref("");
const keyword = ref("");
const showReferences = ref(true);
const maxNodes = ref(260);
const selectedNode = ref(null);
const activeClassName = ref("");
let chart = null;

const CLASS_COLOR = "#2563eb";
const PROPERTY_COLOR = "#16a34a";
const DATA_COLOR = "#f97316";
const PROPERTY_LIMIT_PER_DOMAIN = 30;
const REFERENCE_LIMIT = 100;

const detailFields = [
  { key: "name", label: "name" },
  { key: "label", label: "label" },
  { key: "code", label: "code" },
  { key: "field_name", label: "field_name" },
  { key: "domain", label: "domain" },
  { key: "range", label: "range" },
  { key: "data_type", label: "data_type" },
  { key: "length", label: "length" },
  { key: "constraint", label: "constraint" },
  { key: "reference_code", label: "reference_code" },
  { key: "source.page", label: "source.page" },
  { key: "source.table_index", label: "source.table_index" },
  { key: "source.row_index", label: "source.row_index" },
  { key: "source.filename", label: "source.filename" },
];

const classes = computed(() => Array.isArray(ontology.value?.classes) ? ontology.value.classes : []);
const properties = computed(() => {
  const items = ontology.value?.datatype_properties || ontology.value?.properties || [];
  return Array.isArray(items) ? items : [];
});

const domains = computed(() => {
  const values = new Set();
  for (const item of properties.value) {
    if (item.domain) values.add(String(item.domain));
  }
  for (const item of classes.value) {
    const name = className(item);
    if (name) values.add(name);
  }
  return [...values].sort((a, b) => a.localeCompare(b));
});

const graphData = computed(() => buildGraph());
const graphStats = computed(() => ({
  nodes: graphData.value.nodes.length,
  edges: graphData.value.links.length,
}));

function readOntology() {
  try {
    const raw = localStorage.getItem("lastOntology");
    if (!raw) {
      notice.value = "请先生成本体后再查看图谱。";
      return;
    }
    ontology.value = JSON.parse(raw);
  } catch (err) {
    error.value = "本体 JSON 解析失败，请重新生成本体。";
  }
}

function text(value) {
  return value === undefined || value === null ? "" : String(value);
}

function className(item) {
  return text(item.name || item.id || item.label);
}

function propertyCode(item, index) {
  return text(item.code || item.source_code || item.id || item.name || item.field_name || `property_${index}`);
}

function itemMatches(item) {
  const query = keyword.value.trim().toLowerCase();
  if (!query) return true;
  return [
    item.name,
    item.label,
    item.code,
    item.source_code,
    item.id,
    item.field_name,
    item.domain,
  ].some((value) => text(value).toLowerCase().includes(query));
}

function firstSource(item) {
  const source = item.source && typeof item.source === "object"
    ? item.source
    : Array.isArray(item.sources) && item.sources.length
      ? item.sources[0]
      : {};
  const filename = source.filename || text(source.file_path || source.source_file).split(/[\\/]/).pop();
  return { ...source, filename };
}

function normalizeRaw(item, index) {
  const source = firstSource(item);
  return {
    ...item,
    code: item.code || item.source_code || item.id || item.name || `property_${index}`,
    name: item.name || item.id || item.code || item.field_name || `property_${index}`,
    source,
  };
}

function addNode(nodes, nodeMap, node) {
  if (nodeMap.has(node.id)) return false;
  nodes.push(node);
  nodeMap.set(node.id, node);
  return true;
}

function addLink(links, nodeMap, source, target, label) {
  if (!nodeMap.has(source) || !nodeMap.has(target)) return;
  links.push({ source, target, name: label, label: { show: true, formatter: label } });
}

function selectedClasses() {
  const filtered = selectedDomain.value
    ? classes.value.filter((item) => className(item) === selectedDomain.value)
    : classes.value;
  return filtered.map((item) => ({ item, name: className(item) })).filter((item) => item.name);
}

function propertiesForActiveClass(propertyCapacity) {
  const capacity = Math.max(0, Number(propertyCapacity) || 0);
  if (!capacity || !activeClassName.value) return [];

  const result = [];
  properties.value.forEach((item, index) => {
    if (result.length >= Math.min(PROPERTY_LIMIT_PER_DOMAIN, capacity)) return;
    if (text(item.domain) !== activeClassName.value) return;
    if (!itemMatches(item)) return;
    result.push({ item: normalizeRaw(item, index), index });
  });
  return result;
}

function buildGraph() {
  const nodes = [];
  const links = [];
  const nodeMap = new Map();
  const limit = Math.max(20, Number(maxNodes.value) || 260);

  for (const cls of selectedClasses()) {
    if (nodes.length >= limit) break;
    addNode(nodes, nodeMap, {
      id: `class:${cls.name}`,
      name: cls.item.label || cls.name,
      category: 0,
      symbolSize: 56,
      itemStyle: { color: CLASS_COLOR },
      raw: { ...cls.item, name: cls.name },
    });
  }

  const shownProperties = [];
  const propertyCapacity = Math.floor((limit - nodes.length) / 2);
  for (const { item, index } of propertiesForActiveClass(propertyCapacity)) {
    if (nodes.length + 2 > limit) break;
    const code = propertyCode(item, index);
    const propId = `property:${code}`;
    const dataId = `data:${code}`;
    const label = text(item.label || item.field_name || item.name || code);

    addNode(nodes, nodeMap, {
      id: propId,
      name: label,
      category: 1,
      symbolSize: 38,
      itemStyle: { color: PROPERTY_COLOR },
      raw: item,
    });
    addNode(nodes, nodeMap, {
      id: dataId,
      name: item.code || item.source_code || code,
      category: 2,
      symbolSize: 34,
      itemStyle: { color: DATA_COLOR },
      raw: item,
    });

    addLink(links, nodeMap, `class:${item.domain}`, propId, "domain");
    addLink(links, nodeMap, dataId, `class:${item.domain}`, "rdf:type");
    shownProperties.push(item);
  }

  if (showReferences.value) {
    const byCode = new Map(shownProperties.map((item, index) => [propertyCode(item, index).toLowerCase(), propertyCode(item, index)]));
    let count = 0;
    for (const item of shownProperties) {
      if (count >= REFERENCE_LIMIT) break;
      const sourceCode = propertyCode(item, 0);
      const refs = Array.isArray(item.references) ? item.references : [item.reference_code].filter(Boolean);
      for (const refCode of refs) {
        if (count >= REFERENCE_LIMIT) break;
        const target = text(refCode).toLowerCase();
        if (!target || !byCode.has(target)) continue;
        addLink(links, nodeMap, `data:${sourceCode}`, `data:${byCode.get(target)}`, "references");
        count += 1;
      }
    }
  }

  return { nodes, links };
}

function renderChart() {
  if (!chartRef.value || !ontology.value) return;
  if (!chart) {
    chart = echarts.init(chartRef.value);
    chart.on("click", (params) => {
      if (params.dataType !== "node") return;
      selectedNode.value = params.data;
      if (params.data.category === 0) {
        const name = params.data.raw?.name || params.data.id?.replace("class:", "") || "";
        activeClassName.value = activeClassName.value === name ? "" : name;
      }
    });
  }

  chart.setOption({
    tooltip: {
      formatter(params) {
        if (params.dataType !== "node") return params.data.name || "";
        const type = ["Class", "DatatypeProperty", "DataElement"][params.data.category] || "";
        return `${type}<br/>${params.data.name}`;
      },
    },
    legend: [{ data: ["Class", "DatatypeProperty", "DataElement"], bottom: 0 }],
    series: [{
      type: "graph",
      layout: "force",
      roam: true,
      draggable: true,
      categories: [
        { name: "Class", itemStyle: { color: CLASS_COLOR } },
        { name: "DatatypeProperty", itemStyle: { color: PROPERTY_COLOR } },
        { name: "DataElement", itemStyle: { color: DATA_COLOR } },
      ],
      force: { repulsion: 170, edgeLength: [70, 145], gravity: 0.08 },
      label: { show: true, position: "right", formatter: "{b}", overflow: "truncate", width: 120 },
      edgeSymbol: ["none", "arrow"],
      edgeSymbolSize: 8,
      edgeLabel: { color: "#64748b", fontSize: 11 },
      lineStyle: { color: "#94a3b8", curveness: 0.12, opacity: 0.72 },
      data: graphData.value.nodes,
      links: graphData.value.links,
      emphasis: { focus: "adjacency" },
    }],
  }, true);
}

function readPath(item, path) {
  return path.split(".").reduce((value, key) => value && value[key], item || {});
}

function formatValue(value) {
  if (Array.isArray(value)) return value.join(", ") || "-";
  if (value && typeof value === "object") return JSON.stringify(value);
  return value === undefined || value === null || value === "" ? "-" : value;
}

function resizeChart() {
  chart?.resize();
}

function collapseClass() {
  activeClassName.value = "";
}

watch([graphData, ontology], async () => {
  await nextTick();
  renderChart();
}, { deep: true });

onMounted(async () => {
  readOntology();
  await nextTick();
  renderChart();
  window.addEventListener("resize", resizeChart);
});

onBeforeUnmount(() => {
  window.removeEventListener("resize", resizeChart);
  chart?.dispose();
});
</script>

<style scoped>
.graph-page { max-width: 1280px; margin: 0 auto; padding: 24px; }
.toolbar { display: flex; justify-content: space-between; gap: 16px; margin-bottom: 16px; }
h1 { margin: 0; color: #0f172a; }
.toolbar p { margin: 6px 0 0; color: #64748b; }
.notice, .error { border-radius: 8px; padding: 14px 16px; background: white; border: 1px solid #e2e8f0; }
.notice { color: #0369a1; }
.error { color: #b91c1c; }
.filters { display: grid; grid-template-columns: 220px minmax(220px, 1fr) 170px 150px; gap: 12px; margin-bottom: 14px; align-items: end; }
label { display: flex; flex-direction: column; gap: 6px; color: #475569; font-size: 13px; }
input, select { min-width: 0; width: 100%; padding: 10px 12px; border: 1px solid #cbd5e1; border-radius: 6px; background: white; color: #0f172a; }
.switch { flex-direction: row; align-items: center; gap: 8px; height: 42px; padding: 0 12px; border: 1px solid #cbd5e1; border-radius: 6px; background: white; }
.switch input { width: auto; }
.legend { display: flex; align-items: center; flex-wrap: wrap; gap: 14px; margin-bottom: 14px; color: #475569; }
.legend span, .legend strong { display: inline-flex; align-items: center; gap: 7px; }
.active-class { color: #0f172a; }
.text-btn { padding: 5px 9px; border: 1px solid #cbd5e1; border-radius: 6px; background: white; color: #2563eb; cursor: pointer; }
.text-btn:hover { background: #eff6ff; }
.legend i { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }
.class-dot { background: #2563eb; }
.property-dot { background: #16a34a; }
.data-dot { background: #f97316; }
.graph-layout { display: grid; grid-template-columns: minmax(0, 1fr) 320px; gap: 14px; align-items: stretch; }
.chart-wrap, .detail { background: white; border: 1px solid #e2e8f0; border-radius: 8px; box-shadow: 0 8px 24px rgba(15, 23, 42, .08); }
.chart-wrap { overflow: hidden; }
.chart-scroll { height: 650px; overflow: auto; }
.chart { width: 1360px; max-width: none; height: 920px; min-height: 920px; }
.detail { padding: 16px; overflow: auto; max-height: 650px; }
.detail h2 { margin: 0 0 14px; font-size: 18px; color: #0f172a; }
dl { display: grid; grid-template-columns: 120px minmax(0, 1fr); gap: 9px 10px; margin: 0; }
dt { color: #64748b; }
dd { margin: 0; color: #0f172a; word-break: break-all; }
.detail p { color: #64748b; margin: 0; }
@media (max-width: 1080px) {
  .filters, .graph-layout { grid-template-columns: 1fr; }
  .detail { max-height: none; }
}
@media (max-width: 720px) {
  .graph-page { padding: 16px; }
  .chart-scroll { height: 560px; }
  .chart { width: 980px; height: 760px; min-height: 760px; }
}
</style>








