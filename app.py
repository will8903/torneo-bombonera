from flask import Flask, render_template, request, redirect, send_file
import sqlite3
from fpdf import FPDF
import qrcode
import os
from datetime import datetime
from werkzeug.utils import secure_filename

app = Flask(__name__)

# ==========================================
# CONFIGURACIÓN DE RUTAS ABSOLUTAS PARA RENDER
# ==========================================
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
RUTA_DB = os.path.join(BASE_DIR, 'torneo.db')
CARPETA_COMPROBANTES = os.path.join(BASE_DIR, 'comprobantes')

app.config['UPLOAD_FOLDER'] = CARPETA_COMPROBANTES

# ==========================================
# FUNCIÓN PARA INICIALIZAR LA BASE DE DATOS
# ==========================================
def init_db():
    # Nos aseguramos de que la carpeta de comprobantes exista físicamente
    os.makedirs(CARPETA_COMPROBANTES, exist_ok=True)
    
    conn = sqlite3.connect(RUTA_DB)
    cursor = conn.cursor()
    # Estructura limpia de la tabla
    cursor.execute('''CREATE TABLE IF NOT EXISTS equipos 
        (id INTEGER PRIMARY KEY, nombre_equipo TEXT, ciudad TEXT, telefono TEXT, 
         delegado TEXT, categoria TEXT, fecha_pago TEXT, metodo_pago TEXT, 
         ruta_comprobante TEXT, estado_pago TEXT)''')
    conn.commit()
    conn.close()

# OBLIGAMOS A FLASK A EJECUTAR LA FUNCIÓN APENAS SE ENCIENDA EN INTERNET
with app.app_context():
    init_db()

# ==========================================
# RUTAS DE LA APLICACIÓN
# ==========================================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/inscribir', methods=['POST'])
def inscribir():
    nombre = request.form.get('nombre_equipo')
    ciudad = request.form.get('ciudad')
    telefono = request.form.get('telefono')    
    delegado = request.form.get('delegado')    
    categoria = request.form.get('categoria')
    metodo_pago = request.form.get('metodo_pago')
    
    archivo = request.files.get('comprobante')
    ruta_comprobante = ""
    
    if archivo and archivo.filename != '':
        extension = os.path.splitext(archivo.filename)[1]
        nombre_seguro = secure_filename(f"{nombre}_{metodo_pago}{extension}")
        ruta_comprobante = os.path.join(app.config['UPLOAD_FOLDER'], nombre_seguro)
        archivo.save(ruta_comprobante)
    
    ahora = datetime.now()
    fecha_y_hora_actual = ahora.strftime("%d/%m/%Y %H:%M")
    
    # Corregido: Ahora usa RUTA_DB
    conn = sqlite3.connect(RUTA_DB)
    cursor = conn.cursor()
    cursor.execute('''INSERT INTO equipos 
        (nombre_equipo, ciudad, telefono, delegado, categoria, fecha_pago, metodo_pago, ruta_comprobante, estado_pago) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
        (nombre, ciudad, telefono, delegado, categoria, fecha_y_hora_actual, metodo_pago, ruta_comprobante, 'Pendiente'))
    conn.commit()
    conn.close()
    
    return render_template('espera.html', equipo=nombre)

# PANEL DE CONTROL (ADMIN)
@app.route('/admin/panel')
def panel_admin():
    init_db() 
    
    # Corregido: Ahora apunta correctamente a RUTA_DB
    conn = sqlite3.connect(RUTA_DB)
    cursor = conn.cursor()
    cursor.execute("SELECT id, nombre_equipo, ciudad, delegado, categoria, telefono, metodo_pago, estado_pago FROM equipos")
    lista_equipos = cursor.fetchall()
    conn.commit()
    conn.close()
    return render_template('panel.html', equipos=lista_equipos)

# RUTA PARA APROBAR PAGO Y GENERAR TICKET
@app.route('/admin/aprobar/<int:id>')
def aprobar_y_generar_ticket(id):
    # Corregido: Ahora usa RUTA_DB
    conn = sqlite3.connect(RUTA_DB)
    cursor = conn.cursor()
    
    cursor.execute("UPDATE equipos SET estado_pago = 'Pagado' WHERE id = ?", (id,))
    cursor.execute("SELECT * FROM equipos WHERE id = ?", (id,))
    equipo = cursor.fetchone()
    conn.commit()
    conn.close()

    fecha_registro = equipo[6]
    categoria_equipo = equipo[5]
    metodo_usado = equipo[7]

    # GENERAR EL CÓDIGO QR 
    datos_qr = f"ID: {equipo[0]}\nEquipo: {equipo[1]}\nCategoria: {categoria_equipo}\nPago: {metodo_usado}\nEstado: PAGADO"
    qr_img = qrcode.make(datos_qr)
    
    # Corregido: Ruta absoluta para el QR temporal para evitar bloqueos en Render
    qr_ruta = os.path.join(BASE_DIR, f"qr_temporal_{id}.png")
    qr_img.save(qr_ruta)

    # CONFIGURAR EL PDF OFICIAL (100mm x 150mm)
    pdf = FPDF(format=(100, 150))
    pdf.add_page()
    pdf.set_margins(10, 10, 10)
    
    # Encabezado Amarillo
    pdf.set_fill_color(242, 169, 0) 
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(80, 8, txt="* 4° ANIVERSARIO *", ln=True, align='C', fill=True)
    pdf.ln(2)

    # Bloque Azul: LA BOMBONERA DE RIO SECO
    pdf.set_fill_color(0, 51, 160) 
    pdf.set_text_color(242, 169, 0) 
    pdf.set_font("Arial", 'B', 12) 
    pdf.cell(80, 12, txt="LA BOMBONERA DE RIO SECO", ln=True, align='C', fill=True)
    
    # Fecha y hora
    pdf.set_text_color(255, 255, 255) 
    pdf.set_font("Arial", size=9)
    pdf.cell(80, 6, txt=fecha_registro, ln=True, align='C', fill=True)
    pdf.ln(8)

    # Datos principales
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(80, 7, txt=equipo[1].upper(), ln=True, align='C') 
    pdf.ln(2)
    
    pdf.set_font("Arial", size=11)
    pdf.cell(80, 6, txt=f"Delegado: {equipo[4]}", ln=True, align='C') 
    pdf.cell(80, 6, txt=f"Categoría: {categoria_equipo}", ln=True, align='C') 
    pdf.cell(80, 6, txt=f"Pago: {metodo_usado}", ln=True, align='C') 
    pdf.ln(4)

    # QR CENTRADO Y BAJADO
    pdf.image(qr_ruta, x=34, y=80, w=32, h=32)
    pdf.ln(33) 

    # SELLO PAGO EXITOSO
    pdf.set_text_color(220, 53, 69) 
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(80, 10, txt="PAGO EXITOSO", ln=True, align='C')
    
    # Corregido: Ruta absoluta para el archivo PDF final
    nombre_archivo = os.path.join(BASE_DIR, f"ticket_bombonera_{id}.pdf")
    pdf.output(nombre_archivo)
    
    if os.path.exists(qr_ruta):
        os.remove(qr_ruta)
        
    return send_file(nombre_archivo, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)
