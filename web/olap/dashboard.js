var money = function(value) {
  return new Intl.NumberFormat("es-PE", { style: "currency", currency: "PEN", maximumFractionDigits: 0 }).format(value);
};
function renderBars(target, rows, labelKey) {
  var max = Math.max.apply(null, rows.map(function(row) { return row.revenue; }).concat([1]));
  document.querySelector(target).innerHTML = rows.map(function(row) {
    var width = Math.max(3, row.revenue / max * 100);
    return '<div class="bar-row"><span>' + row[labelKey] + '</span><div class="bar-track" role="img" aria-label="' + row[labelKey] + ': ' + money(row.revenue) + '"><div class="bar-fill" style="width:' + width + '%"></div></div><span class="bar-value">' + money(row.revenue) + '</span></div>';
  }).join("");
}
fetch("../data/olap.json").then(function(response) {
  if (!response.ok) throw new Error("Dashboard data has not been built yet.");
  return response.json();
}).then(function(data) {
  document.querySelector("#orders").textContent = data.orders.toLocaleString();
  document.querySelector("#revenue").textContent = money(data.revenue);
  document.querySelector("#aov").textContent = money(data.average_order_value);
  document.querySelector("#facts").textContent = data.dimensions.fact_rows.toLocaleString();
  renderBars("#monthly", data.monthly, "year_month");
  renderBars("#region", data.by_region, "region");
  document.querySelector("#detail").innerHTML = data.detail.map(function(row) {
    return "<tr><td>" + row.year_month + "</td><td>" + row.region + "</td><td>" + row.category + "</td><td>" + row.product + "</td><td>" + row.units + "</td><td>" + money(row.revenue) + "</td></tr>";
  }).join("");
}).catch(function(error) {
  for (var id of ["orders", "revenue", "aov", "facts"]) document.querySelector("#" + id).textContent = "—";
  document.querySelector("#detail").innerHTML = '<tr><td colspan="6" class="error">' + error.message + "</td></tr>";
});
