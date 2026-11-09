// app.js - Cliente Frontend Vanilla JS con Fetch API

const STORAGE_TOKEN_KEY = "asistencia_auth_token";

const state = {
    token: localStorage.getItem(STORAGE_TOKEN_KEY) || null,
    usuario: null,
    horarioLimite: "08:15",
    materiaDefault: "Programación III",
    alumnos: [],
    fechaFiltroActual: obtenerFechaLocalISO(),
};

// =====================================================================
// UTILIDADES GENERALES Y FETCH AUTENTICADO
// =====================================================================

function obtenerFechaLocalISO() {
    const ahora = new Date();
    const anio = ahora.getFullYear();
    const mes = String(ahora.getMonth() + 1).padStart(2, "0");
    const dia = String(ahora.getDate()).padStart(2, "0");
    return `${anio}-${mes}-${dia}`;
}

function obtenerHoraLocalHHMM() {
    const ahora = new Date();
    const horas = String(ahora.getHours()).padStart(2, "0");
    const minutos = String(ahora.getMinutes()).padStart(2, "0");
    return `${horas}:${minutos}`;
}

function escapeHtml(texto) {
    const div = document.createElement("div");
    div.textContent = texto == null ? "" : String(texto);
    return div.innerHTML;
}

function mostrarToast(mensaje, tipo = "success") {
    const contenedor = document.getElementById("toast-container");
    const toast = document.createElement("div");
    toast.className = `toast ${tipo}`;
    toast.textContent = mensaje;
    contenedor.appendChild(toast);

    setTimeout(() => {
        toast.remove();
    }, 3800);
}

async function apiFetch(endpoint, options = {}) {
    const headers = {
        "Content-Type": "application/json",
        ...(options.headers || {}),
    };

    if (state.token) {
        headers["Authorization"] = `Bearer ${state.token}`;
    }

    const respuesta = await fetch(endpoint, {
        ...options,
        headers,
    });

    let payload = null;
    try {
        payload = await respuesta.json();
    } catch (_) {
        payload = null;
    }

    if (respuesta.status === 401 && endpoint !== "/api/auth/login") {
        limpiarSesionLocal();
        mostrarPantallaLogin();
        throw new Error((payload && payload.detail) || "Sesión expirada. Inicie sesión nuevamente.");
    }

    if (!respuesta.ok) {
        const mensajeError =
            (payload && (payload.detail || payload.mensaje)) ||
            `Error en la solicitud (HTTP ${respuesta.status})`;
        throw new Error(typeof mensajeError === "string" ? mensajeError : JSON.stringify(mensajeError));
    }

    return payload;
}

// =====================================================================
// GESTIÓN DE SESIÓN Y PANTALLAS
// =====================================================================

function guardarSesionLocal(token, usuario) {
    state.token = token;
    state.usuario = usuario;
    localStorage.setItem(STORAGE_TOKEN_KEY, token);
}

function limpiarSesionLocal() {
    state.token = null;
    state.usuario = null;
    localStorage.removeItem(STORAGE_TOKEN_KEY);
}

function mostrarPantallaLogin() {
    document.getElementById("app-screen").classList.add("hidden");
    document.getElementById("login-screen").classList.remove("hidden");
}

function mostrarPantallaSistema() {
    document.getElementById("login-screen").classList.add("hidden");
    document.getElementById("app-screen").classList.remove("hidden");

    if (state.usuario) {
        document.getElementById("user-display").textContent =
            `${state.usuario.nombre_completo} (@${state.usuario.username})`;
    }
}

async function inicializarAplicacion() {
    inicializarCamposFechaHora();
    configurarEventosUI();

    if (!state.token) {
        mostrarPantallaLogin();
        return;
    }

    try {
        const usuario = await apiFetch("/api/auth/me");
        state.usuario = usuario;
        mostrarPantallaSistema();
        await cargarDatosInicialesPanel();
    } catch (_) {
        limpiarSesionLocal();
        mostrarPantallaLogin();
    }
}

function inicializarCamposFechaHora() {
    const hoy = obtenerFechaLocalISO();
    const ahora = obtenerHoraLocalHHMM();

    document.getElementById("asistencia-fecha").value = hoy;
    document.getElementById("asistencia-hora").value = ahora;
    document.getElementById("filtro-fecha-dia").value = hoy;
}

async function cargarDatosInicialesPanel() {
    await Promise.all([
        cargarConfiguracion(),
        cargarAlumnos(),
        cargarAsistenciasDia(state.fechaFiltroActual),
    ]);
    actualizarPrevisualizacionEstado();
}

// =====================================================================
// CONFIGURACIÓN DE HORARIO LÍMITE Y CÁLCULO EN VIVO
// =====================================================================

async function cargarConfiguracion() {
    const config = await apiFetch("/api/configuracion");
    state.horarioLimite = config.horario_limite;
    state.materiaDefault = config.materia_default;

    document.getElementById("header-horario-limite").textContent = config.horario_limite;
    document.getElementById("config-horario").value = config.horario_limite;
    document.getElementById("config-materia").value = config.materia_default;
    document.getElementById("asistencia-materia").value = config.materia_default;
    actualizarPrevisualizacionEstado();
}

function actualizarPrevisualizacionEstado() {
    const preview = document.getElementById("live-status-preview");
    const modo = document.getElementById("asistencia-estado").value;
    const hora = document.getElementById("asistencia-hora").value || obtenerHoraLocalHHMM();

    let estadoResultante = "presente";
    if (modo === "ausente") {
        estadoResultante = "ausente";
    } else if (modo === "presente") {
        estadoResultante = "presente";
    } else if (modo === "tardanza") {
        estadoResultante = "tardanza";
    } else {
        estadoResultante = hora > state.horarioLimite ? "tardanza" : "presente";
    }

    preview.className = `badge badge-${estadoResultante}`;
    if (modo === "auto") {
        preview.textContent = `Auto: ${estadoResultante.toUpperCase()} (Límite ${state.horarioLimite})`;
    } else {
        preview.textContent = `Manual: ${estadoResultante.toUpperCase()}`;
    }
}

// =====================================================================
// GESTIÓN DE ALUMNOS (CRUD)
// =====================================================================

async function cargarAlumnos(filtro = "") {
    const query = filtro ? `?q=${encodeURIComponent(filtro)}` : "";
    const lista = await apiFetch(`/api/alumnos${query}`);

    if (!filtro) {
        state.alumnos = lista;
        renderizarSelectorRapidoAlumnos(lista);
    }

    renderizarTablaAlumnos(lista);
}

function renderizarSelectorRapidoAlumnos(alumnos) {
    const datalist = document.getElementById("datalist-alumnos");
    const chipsContainer = document.getElementById("quick-alumnos-chips");

    datalist.innerHTML = alumnos
        .map(
            (a) =>
                `<option value="${escapeHtml(a.dni)}">${escapeHtml(a.apellido)}, ${escapeHtml(a.nombre)} (${escapeHtml(a.curso)})</option>`
        )
        .join("");

    if (alumnos.length === 0) {
        chipsContainer.innerHTML = `<span class="help-text">No hay alumnos cargados aún.</span>`;
        return;
    }

    chipsContainer.innerHTML = alumnos
        .map(
            (a) => `
            <button type="button" class="chip-alumno" data-dni="${escapeHtml(a.dni)}">
                <strong>${escapeHtml(a.dni)}</strong> · ${escapeHtml(a.apellido)}, ${escapeHtml(a.nombre)}
            </button>
        `
        )
        .join("");

    chipsContainer.querySelectorAll(".chip-alumno").forEach((chip) => {
        chip.addEventListener("click", () => {
            const dni = chip.getAttribute("data-dni");
            document.getElementById("asistencia-dni").value = dni;
            document.getElementById("asistencia-dni").focus();
        });
    });
}

function renderizarTablaAlumnos(alumnos) {
    const tbody = document.getElementById("tabla-alumnos");
    if (alumnos.length === 0) {
        tbody.innerHTML = `<tr><td colspan="4" class="empty-row">No se encontraron alumnos registrados.</td></tr>`;
        return;
    }

    tbody.innerHTML = alumnos
        .map(
            (a) => `
            <tr>
                <td><strong>${escapeHtml(a.dni)}</strong></td>
                <td>${escapeHtml(a.apellido)}, ${escapeHtml(a.nombre)}</td>
                <td>${escapeHtml(a.curso)}</td>
                <td>
                    <div class="table-actions">
                        <button type="button" class="btn btn-outline btn-sm btn-ver-informe" data-dni="${escapeHtml(a.dni)}">
                            Informe
                        </button>
                        <button
                            type="button"
                            class="btn btn-outline btn-sm btn-editar-alumno"
                            data-dni="${escapeHtml(a.dni)}"
                            data-nombre="${escapeHtml(a.nombre)}"
                            data-apellido="${escapeHtml(a.apellido)}"
                            data-curso="${escapeHtml(a.curso)}"
                        >
                            Editar
                        </button>
                        <button type="button" class="btn btn-danger btn-sm btn-borrar-alumno" data-dni="${escapeHtml(a.dni)}">
                            Borrar
                        </button>
                    </div>
                </td>
            </tr>
        `
        )
        .join("");

    tbody.querySelectorAll(".btn-ver-informe").forEach((btn) => {
        btn.addEventListener("click", () => {
            const dni = btn.getAttribute("data-dni");
            activarPestana("tab-reporte");
            document.getElementById("reporte-dni-input").value = dni;
            consultarReporteAlumno(dni);
        });
    });

    tbody.querySelectorAll(".btn-editar-alumno").forEach((btn) => {
        btn.addEventListener("click", () => {
            activarModoEdicionAlumno({
                dni: btn.getAttribute("data-dni"),
                nombre: btn.getAttribute("data-nombre"),
                apellido: btn.getAttribute("data-apellido"),
                curso: btn.getAttribute("data-curso"),
            });
        });
    });

    tbody.querySelectorAll(".btn-borrar-alumno").forEach((btn) => {
        btn.addEventListener("click", async () => {
            const dni = btn.getAttribute("data-dni");
            if (!window.confirm(`¿Confirma eliminar al alumno con DNI ${dni} y todo su historial?`)) {
                return;
            }
            try {
                const res = await apiFetch(`/api/alumnos/${encodeURIComponent(dni)}`, {
                    method: "DELETE",
                });
                mostrarToast(res.mensaje, "success");
                resetearFormularioAlumno();
                await Promise.all([
                    cargarAlumnos(document.getElementById("buscar-alumno-input").value.trim()),
                    cargarAsistenciasDia(state.fechaFiltroActual),
                ]);
            } catch (err) {
                mostrarToast(err.message, "error");
            }
        });
    });
}

function activarModoEdicionAlumno(alumno) {
    document.getElementById("alumno-modo-edicion").value = "true";
    document.getElementById("form-alumno-titulo").textContent = `Editar Alumno (DNI ${alumno.dni})`;
    const inputDni = document.getElementById("alumno-dni");
    inputDni.value = alumno.dni;
    inputDni.disabled = true;

    document.getElementById("alumno-nombre").value = alumno.nombre;
    document.getElementById("alumno-apellido").value = alumno.apellido;
    document.getElementById("alumno-curso").value = alumno.curso;
    document.getElementById("btn-guardar-alumno").textContent = "Actualizar Datos";
    document.getElementById("btn-cancelar-edicion").classList.remove("hidden");
}

function resetearFormularioAlumno() {
    document.getElementById("form-alumno").reset();
    document.getElementById("alumno-modo-edicion").value = "false";
    document.getElementById("form-alumno-titulo").textContent = "Agregar Nuevo Alumno";
    document.getElementById("alumno-dni").disabled = false;
    document.getElementById("btn-guardar-alumno").textContent = "Guardar Alumno";
    document.getElementById("btn-cancelar-edicion").classList.add("hidden");
}

// =====================================================================
// REGISTRO Y LISTADO DE ASISTENCIAS POR DÍA
// =====================================================================

async function cargarAsistenciasDia(fechaConsulta) {
    state.fechaFiltroActual = fechaConsulta;
    const param = encodeURIComponent(fechaConsulta);
    const data = await apiFetch(`/api/asistencias?fecha=${param}`);

    document.getElementById("dia-total").textContent = data.resumen.total;
    document.getElementById("dia-presentes").textContent = data.resumen.presentes;
    document.getElementById("dia-tardanzas").textContent = data.resumen.tardanzas;
    document.getElementById("dia-ausentes").textContent = data.resumen.ausentes;

    const tbody = document.getElementById("tabla-asistencias-dia");
    if (data.registros.length === 0) {
        const etiquetaFecha = fechaConsulta === "todas" ? "el historial" : `la fecha ${fechaConsulta}`;
        tbody.innerHTML = `<tr><td colspan="9" class="empty-row">Sin asistencias registradas para ${escapeHtml(etiquetaFecha)}.</td></tr>`;
        return;
    }

    tbody.innerHTML = data.registros
        .map(
            (r) => `
            <tr>
                <td>${escapeHtml(r.fecha)}</td>
                <td>${escapeHtml(r.hora)}</td>
                <td><strong>${escapeHtml(r.dni)}</strong></td>
                <td>${escapeHtml(r.apellido)}, ${escapeHtml(r.nombre)}</td>
                <td>${escapeHtml(r.curso)}</td>
                <td>${escapeHtml(r.materia)}</td>
                <td><span class="badge badge-${escapeHtml(r.estado)}">${escapeHtml(r.estado)}</span></td>
                <td>${escapeHtml(r.observacion || "-")}</td>
                <td>
                    <button type="button" class="btn btn-outline btn-sm btn-borrar-asistencia" data-id="${r.id}">
                        Quitar
                    </button>
                </td>
            </tr>
        `
        )
        .join("");

    tbody.querySelectorAll(".btn-borrar-asistencia").forEach((btn) => {
        btn.addEventListener("click", async () => {
            const id = btn.getAttribute("data-id");
            if (!window.confirm("¿Desea eliminar este registro de asistencia?")) {
                return;
            }
            try {
                const res = await apiFetch(`/api/asistencias/${id}`, { method: "DELETE" });
                mostrarToast(res.mensaje, "success");
                await cargarAsistenciasDia(state.fechaFiltroActual);
            } catch (err) {
                mostrarToast(err.message, "error");
            }
        });
    });
}

// =====================================================================
// INFORME ESTADÍSTICO POR ALUMNO
// =====================================================================

async function consultarReporteAlumno(dni) {
    const dniLimpio = (dni || "").trim();
    if (!dniLimpio) {
        mostrarToast("Ingrese un DNI para consultar el informe.", "error");
        return;
    }

    try {
        const data = await apiFetch(`/api/reportes/alumno/${encodeURIComponent(dniLimpio)}`);
        document.getElementById("reporte-empty").classList.add("hidden");
        document.getElementById("reporte-resultado").classList.remove("hidden");

        document.getElementById("rep-nombre-completo").textContent =
            `${data.alumno.apellido}, ${data.alumno.nombre}`;
        document.getElementById("rep-meta-info").textContent = `DNI: ${data.alumno.dni}`;
        document.getElementById("rep-curso-badge").textContent = data.alumno.curso;

        const est = data.estadisticas;
        document.getElementById("rep-total").textContent = est.total_registros;
        document.getElementById("rep-presentes").textContent = est.presentes;
        document.getElementById("rep-tardanzas").textContent = est.tardanzas;
        document.getElementById("rep-ausentes").textContent = est.ausentes;

        document.getElementById("rep-pct-presentes").textContent = `${est.porcentaje_presentes}%`;
        document.getElementById("rep-pct-tardanzas").textContent = `${est.porcentaje_tardanzas}%`;
        document.getElementById("rep-pct-ausentes").textContent = `${est.porcentaje_ausentes}%`;

        document.getElementById("bar-presentes").style.width = `${est.porcentaje_presentes}%`;
        document.getElementById("bar-tardanzas").style.width = `${est.porcentaje_tardanzas}%`;
        document.getElementById("bar-ausentes").style.width = `${est.porcentaje_ausentes}%`;

        const tbody = document.getElementById("tabla-historial-alumno");
        if (data.historial.length === 0) {
            tbody.innerHTML = `<tr><td colspan="5" class="empty-row">El alumno aún no registra asistencias cargadas.</td></tr>`;
        } else {
            tbody.innerHTML = data.historial
                .map(
                    (h) => `
                    <tr>
                        <td><strong>${escapeHtml(h.fecha)}</strong></td>
                        <td>${escapeHtml(h.hora)}</td>
                        <td><span class="badge badge-${escapeHtml(h.estado)}">${escapeHtml(h.estado)}</span></td>
                        <td>${escapeHtml(h.materia)}</td>
                        <td>${escapeHtml(h.observacion || "-")}</td>
                    </tr>
                `
                )
                .join("");
        }
    } catch (err) {
        mostrarToast(err.message, "error");
    }
}

// =====================================================================
// EVENTOS DE LA INTERFAZ DE USUARIO
// =====================================================================

function activarPestana(tabId) {
    document.querySelectorAll(".nav-tab").forEach((btn) => {
        btn.classList.toggle("active", btn.getAttribute("data-tab") === tabId);
    });
    document.querySelectorAll(".tab-panel").forEach((panel) => {
        panel.classList.toggle("active", panel.id === tabId);
    });
}

function configurarEventosUI() {
    // Autocompletar credenciales demo
    document.getElementById("btn-fill-demo").addEventListener("click", () => {
        document.getElementById("login-username").value = "docente";
        document.getElementById("login-password").value = "docente123";
        document.getElementById("login-error").classList.add("hidden");
    });

    // Login submit
    document.getElementById("login-form").addEventListener("submit", async (e) => {
        e.preventDefault();
        const errorBox = document.getElementById("login-error");
        errorBox.classList.add("hidden");

        const username = document.getElementById("login-username").value.trim();
        const password = document.getElementById("login-password").value;

        try {
            const data = await apiFetch("/api/auth/login", {
                method: "POST",
                body: JSON.stringify({ username, password }),
            });
            guardarSesionLocal(data.access_token, data.usuario);
            document.getElementById("login-form").reset();
            inicializarCamposFechaHora();
            mostrarPantallaSistema();
            await cargarDatosInicialesPanel();
            mostrarToast(`Bienvenido/a, ${data.usuario.nombre_completo}`, "success");
        } catch (err) {
            errorBox.textContent = err.message;
            errorBox.classList.remove("hidden");
        }
    });

    // Logout
    document.getElementById("btn-logout").addEventListener("click", async () => {
        try {
            await apiFetch("/api/auth/logout", { method: "POST" });
        } catch (_) {
            // Limpiamos sesión local incluso si el token ya había expirado
        }
        limpiarSesionLocal();
        mostrarPantallaLogin();
        mostrarToast("Sesión cerrada correctamente.", "success");
    });

    // Navegación por pestañas
    document.querySelectorAll(".nav-tab").forEach((tab) => {
        tab.addEventListener("click", () => {
            activarPestana(tab.getAttribute("data-tab"));
        });
    });

    // Previsualización en vivo de tardanza / presente
    document.getElementById("asistencia-hora").addEventListener("input", actualizarPrevisualizacionEstado);
    document.getElementById("asistencia-estado").addEventListener("change", actualizarPrevisualizacionEstado);

    // Guardar configuración de horario límite
    document.getElementById("form-configuracion").addEventListener("submit", async (e) => {
        e.preventDefault();
        const horario_limite = document.getElementById("config-horario").value;
        const materia_default = document.getElementById("config-materia").value.trim();

        try {
            const res = await apiFetch("/api/configuracion", {
                method: "PUT",
                body: JSON.stringify({ horario_limite, materia_default }),
            });
            state.horarioLimite = res.configuracion.horario_limite;
            state.materiaDefault = res.configuracion.materia_default;
            document.getElementById("header-horario-limite").textContent = state.horarioLimite;
            document.getElementById("asistencia-materia").value = state.materiaDefault;
            actualizarPrevisualizacionEstado();
            mostrarToast(`Horario límite actualizado a ${state.horarioLimite}.`, "success");
        } catch (err) {
            mostrarToast(err.message, "error");
        }
    });

    // Registrar asistencia
    document.getElementById("form-asistencia").addEventListener("submit", async (e) => {
        e.preventDefault();
        const dni = document.getElementById("asistencia-dni").value.trim();
        const fecha = document.getElementById("asistencia-fecha").value;
        const hora = document.getElementById("asistencia-hora").value;
        const modoEstado = document.getElementById("asistencia-estado").value;
        const materia = document.getElementById("asistencia-materia").value.trim();
        const observacion = document.getElementById("asistencia-observacion").value.trim();

        const forzar_estado = modoEstado !== "auto";

        try {
            const res = await apiFetch("/api/asistencias", {
                method: "POST",
                body: JSON.stringify({
                    dni,
                    fecha,
                    hora,
                    estado: modoEstado,
                    materia,
                    observacion,
                    forzar_estado,
                }),
            });
            mostrarToast(
                `${res.mensaje} (${res.registro.apellido}, ${res.registro.nombre})`,
                "success"
            );
            document.getElementById("asistencia-dni").value = "";
            document.getElementById("asistencia-observacion").value = "";
            document.getElementById("filtro-fecha-dia").value = fecha;
            await cargarAsistenciasDia(fecha);
        } catch (err) {
            mostrarToast(err.message, "error");
        }
    });

    // Filtros de asistencias del día
    document.getElementById("btn-filtrar-dia").addEventListener("click", () => {
        const fecha = document.getElementById("filtro-fecha-dia").value || obtenerFechaLocalISO();
        cargarAsistenciasDia(fecha);
    });

    document.getElementById("btn-ver-hoy").addEventListener("click", () => {
        const hoy = obtenerFechaLocalISO();
        document.getElementById("filtro-fecha-dia").value = hoy;
        cargarAsistenciasDia(hoy);
    });

    document.getElementById("btn-ver-todas").addEventListener("click", () => {
        cargarAsistenciasDia("todas");
    });

    // Informe por alumno
    document.getElementById("form-buscar-reporte").addEventListener("submit", (e) => {
        e.preventDefault();
        const dni = document.getElementById("reporte-dni-input").value;
        consultarReporteAlumno(dni);
    });

    // Alta y edición de alumnos
    document.getElementById("form-alumno").addEventListener("submit", async (e) => {
        e.preventDefault();
        const esEdicion = document.getElementById("alumno-modo-edicion").value === "true";
        const dni = document.getElementById("alumno-dni").value.trim();
        const nombre = document.getElementById("alumno-nombre").value.trim();
        const apellido = document.getElementById("alumno-apellido").value.trim();
        const curso = document.getElementById("alumno-curso").value.trim();

        try {
            if (esEdicion) {
                const res = await apiFetch(`/api/alumnos/${encodeURIComponent(dni)}`, {
                    method: "PUT",
                    body: JSON.stringify({ nombre, apellido, curso }),
                });
                mostrarToast(res.mensaje, "success");
            } else {
                const res = await apiFetch("/api/alumnos", {
                    method: "POST",
                    body: JSON.stringify({ dni, nombre, apellido, curso }),
                });
                mostrarToast(res.mensaje, "success");
            }
            resetearFormularioAlumno();
            await cargarAlumnos();
            document.getElementById("buscar-alumno-input").value = "";
        } catch (err) {
            mostrarToast(err.message, "error");
        }
    });

    document.getElementById("btn-cancelar-edicion").addEventListener("click", () => {
        resetearFormularioAlumno();
    });

    document.getElementById("buscar-alumno-input").addEventListener("input", (e) => {
        cargarAlumnos(e.target.value.trim());
    });
}

document.addEventListener("DOMContentLoaded", inicializarAplicacion);
