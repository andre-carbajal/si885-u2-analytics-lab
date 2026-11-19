fetch("../data/pipeline.json").then(function(response) {
  if (!response.ok) throw new Error("Report is not available yet.");
  return response.json();
}).then(function(report) {
  document.querySelector("#rows").textContent = report.curated_rows.toLocaleString();
  document.querySelector("#revenue").textContent = new Intl.NumberFormat("es-PE", { style: "currency", currency: "PEN" }).format(report.total_revenue);
  document.querySelector("#checks").textContent = report.invalid_rows + " / " + report.duplicate_ids;
}).catch(function(error) {
  document.querySelector("#rows").textContent = "Unavailable";
  document.querySelector("#revenue").textContent = "—";
  document.querySelector("#checks").textContent = error.message;
  document.querySelector("#checks").classList.add("error");
});
