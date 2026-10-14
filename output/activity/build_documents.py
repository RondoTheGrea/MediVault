from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from reportlab.platypus import Paragraph, Table, TableStyle
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader
from PIL import Image
import pypdfium2 as pdfium
import zipfile

ROOT = Path(__file__).parent
W, H = 1100, 950
NAVY, BLUE, INK, MUTED = '#12314C', '#2160A1', '#203343', '#5A6B79'
style = ParagraphStyle('body', fontName='Helvetica', fontSize=18, leading=27, textColor=HexColor(INK))
small = ParagraphStyle('small', parent=style, fontSize=15, leading=23)

def para(c, text, x, y, width=1000, st=style):
    p = Paragraph(text, st)
    _, height = p.wrap(width, H)
    p.drawOn(c, x, y-height)
    return y-height

def base(c, title, subtitle, num, label='SYSTEM SCREENSHOTS & USER GUIDE'):
    c.setFillColor(HexColor('#F5F8FC')); c.rect(0,0,W,H,fill=1,stroke=0)
    c.setFillColor(HexColor(NAVY)); c.rect(0,H-145,W,145,fill=1,stroke=0)
    c.setFillColor(HexColor('#7DCADB')); c.setFont('Helvetica-Bold',13)
    c.drawString(50,H-35,'MEDIVAULT  /  '+label)
    c.setFillColor(HexColor('#FFFFFF')); c.setFont('Helvetica-Bold',31)
    c.drawString(50,H-82,title)
    c.setFont('Helvetica',17); c.drawString(50,H-115,subtitle)
    c.setStrokeColor(HexColor('#D8E2EB')); c.line(50,53,W-50,53)
    c.setFillColor(HexColor(MUTED)); c.setFont('Helvetica',12)
    footer='MediVault | Fictional seeded demo data | Single-tab captures' if label=='SYSTEM SCREENSHOTS & USER GUIDE' else 'MediVault | Flask + SQLite | Project documentation'
    c.drawString(50,30,footer)
    c.drawRightString(W-50,30,f'{num:02d}')

def shot(c, filename, top=775, maxh=590):
    path = ROOT/'screenshots'/filename
    im = Image.open(path); iw,ih=im.size
    scale=min(1000/iw,maxh/ih)
    width,height=iw*scale,ih*scale
    x=(W-width)/2; y=top-height
    c.setFillColor(HexColor('#FFFFFF')); c.setStrokeColor(HexColor('#D8E2EB'))
    c.roundRect(x-3,y-3,width+6,height+6,8,fill=1,stroke=1)
    c.drawImage(ImageReader(im),x,y,width,height)
    return y

features = [
('Sign in to MediVault','01-login.jpg','Secure entry to the system','Enter your assigned username and password, then select <b>Log in</b>. The landing page and available controls depend on your role.','The screenshots use the fictional records and accounts supplied in seed.py.'),
('Find a patient','03-patients.jpg','Search and open patient records','Select <b>Patients</b>, enter a name in the search box, and select <b>Search</b>. Choose <b>Open</b> to view a chart, or <b>Emergency</b> when your role permits it.','The physician view shows routine and emergency entry points.'),
('Register a patient','10-registration.jpg','Records Staff workflow','Sign in as Records Staff and select <b>+ Register patient</b>. Fill in first name, last name, birth date, and sex. Add contact details and select <b>Save</b>.','Fields marked * are required. Cancel returns to the patient list.'),
('Read the clinical chart','06-clinical-chart.jpg','Physician view of the complete patient record','Open a patient as a physician to see the profile, allergies, medications, and medical history. Use the section-specific <b>Add</b> or <b>Edit</b> controls to update permitted records.','Medication status distinguishes current treatment from past treatment.'),
('Add a medication','07-medication-form.jpg','A simple clinical data-entry form','From the patient chart, select <b>+ Add medication</b>. Enter the name, dosage, and frequency; choose <b>current</b> or <b>past</b>; then select <b>Save</b>.','Physicians and nurses can maintain medications. This screenshot shows the form without changing a record.'),
('Respect role permissions','04-role-restrictions.jpg','Administrator view with clinical sections hidden','When a section says <b>Hidden for your role</b>, use an account with the appropriate assigned role. Administrators manage oversight and staff accounts; their default role cannot read clinical sections.','Records Staff can maintain patient profiles but cannot read allergies, medications, or medical history.'),
('Give a reason for emergency access','08-emergency-reason.jpg','Accountable access to essential information','Select <b>Emergency</b> or <b>Emergency access</b>. Describe the emergency using at least 10 characters, then select <b>Open emergency information</b>.','This capture uses an explicitly labelled classroom demonstration reason with seeded demo data.'),
('View emergency essentials','09-emergency-summary.jpg','Allergies, current medications, and emergency contact','Review the patient identity, blood type, emergency contact, allergies, and current medications. Select <b>Back to patient list</b> when finished.','The emergency view excludes past medications and medical history. The reason and access time are recorded.'),
('Monitor the dashboard','02-dashboard.jpg','Administrator overview','Sign in as an administrator and select <b>Dashboard</b>. Review patient and active-staff totals, access counts, and recent emergency accesses. Select <b>See all</b> for the emergency audit list.','The displayed totals reflect the seeded records and this documentation walkthrough.'),
('Review and export the audit log','11-audit-log.jpg','Routine and emergency access are traceable','Select <b>Audit log</b>. Choose an access type and optionally enter part of a username, then select <b>Filter</b>. Select <b>Export CSV</b> to download the filtered log.','Each entry identifies the time, staff member, patient, access type, action, and reason.'),
('Manage staff accounts','05-users.jpg','Administrator-only account management','Select <b>Users</b> and <b>+ New user</b>. Enter the account details, choose a role, and save. Use <b>Deactivate</b> to disable an existing account or <b>Activate</b> to restore it.','Accounts are deactivated instead of deleted so past audit entries keep their staff references.'),
]

dest=ROOT/'MediVault-System-Screenshots-and-User-Guide.pdf'
c=canvas.Canvas(str(dest),pagesize=(W,H)); c.setTitle('MediVault - System Screenshots and User Guide')
for n,(title,file,sub,instructions,note) in enumerate(features,1):
    base(c,title,sub,n)
    shot(c,file)
    para(c,instructions,50,165,1000)
    para(c,note,50,90,1000,small)
    c.showPage()

base(c,'Run the system','Windows setup and daily use',12)
y=775
for title,body in [
('1. Prepare Python','Install Python 3.11 or newer. Open a terminal in the MediVault project folder.'),
('2. Create the environment','If .venv does not exist, run <font face="Courier">python -m venv .venv</font>.'),
('3. Install dependencies','Run <font face="Courier">.venv\\Scripts\\python.exe -m pip install -r requirements.txt</font>.'),
('4. Start MediVault','Run <font face="Courier">.venv\\Scripts\\python.exe -m flask --app app run --host 127.0.0.1 --port 5000</font>.'),
('5. Open the browser','Keep the terminal running. Open <b>http://127.0.0.1:5000</b> and sign in with an assigned account.'),
('6. Finish safely','Select <b>Log out</b> when finished. To stop the local server, press <b>Ctrl+C</b> in its terminal.'),
]:
    y=para(c,'<b>'+title+'</b>',50,y); y=para(c,body,50,y-4); y-=22
para(c,'On first launch, the system creates instance/ with the database, keys, roles, and demo data. Keep the instance folder to preserve records and encryption keys.',50,180,1000,small)
para(c,'If the page cannot load: check that the server is still running, use http (not https), and check for another process using port 5000. A local server started in a restricted sandbox may be unreachable from your browser.',50,125,1000,small)
c.showPage()

base(c,'Demo accounts and role guide','Use the account that matches the task',13)
rows=[['Role','Username','Demo password','Allowed workflow'],
['Administrator','admin','Admin1234','Dashboard, audit logs, staff accounts; patient profiles'],
['Physician','dr.reyes','Doctor1234','Clinical charts, profile edits, medical records, emergency access'],
['Nurse','nurse.cruz','Nurse1234','Read history; maintain allergies and medications; emergency access'],
['Records Staff','records.lim','Records1234','Register, edit, and delete patient profiles'],
['Emergency Responder','medic.tan','Medic1234','Patient lookup and emergency essentials only']]
table=Table([[Paragraph(v,small) for v in row] for row in rows],colWidths=[185,150,170,495])
table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),HexColor('#DFEAF5')),('VALIGN',(0,0),(-1,-1),'TOP'),('TOPPADDING',(0,0),(-1,-1),17),('BOTTOMPADDING',(0,0),(-1,-1),17),('LEFTPADDING',(0,0),(-1,-1),12),('LINEBELOW',(0,0),(-1,-1),.5,HexColor('#D8E2EB'))]))
_,th=table.wrap(1000,700);table.drawOn(c,50,775-th)
y=775-th-35
y=para(c,'<b>Clinical updates</b><br/>Physicians can add or edit history, allergies, and medications. Nurses can read history and maintain allergies and medications. Records Staff maintain demographic profiles.',50,y)
y=para(c,'<b>Emergency access</b><br/>Available to physicians, nurses, and responders. Give a clear reason. The system records the access for administrator review.',50,y-24)
para(c,'<b>Account note</b><br/>These are the project\'s seeded demonstration credentials. New accounts are created by an administrator. Deactivated accounts cannot sign in.',50,y-24)
c.showPage();c.save()

dest=ROOT/'MediVault-Group-Contribution.pdf'
c=canvas.Canvas(str(dest),pagesize=(W,H));c.setTitle('MediVault - Group Contribution')
base(c,'Group Contribution','Project: MediVault medical information management system',1,'GROUP CONTRIBUTION')
y=775
y=para(c,'<b>Jabyn Obrero</b>',50,y)
y=para(c,'Co-developed the domain classes in <b>models.py</b> with Vien Paje.',50,y-8)
y=para(c,'<b>Vien Paje</b>',50,y-35)
y=para(c,'Co-developed the domain classes in <b>models.py</b> with Jabyn Obrero.',50,y-8)
y=para(c,'<b>Shared models.py classes</b>',50,y-30)
y=para(c,'Permission, Role, User, Patient, MedicalRecord, HistoryEntry, Allergy, Medication, PatientProfile, and EmergencySummary.',50,y-8)
y=para(c,'These classes define permissions and users, patient information, clinical record types, role-specific profiles, and emergency summaries. The clinical records use inheritance and shared methods for record details and emergency relevance.',50,y-12,1000,small)
y=para(c,'<b>Ronald Dean Sanchez</b>',50,y-35)
y=para(c,'Developed all remaining project components:',50,y-8)
for line in [
'<b>app.py, templates/, static/:</b> Flask routes, web pages, navigation, and visual styling.',
'<b>database.py, repositories.py, seed.py:</b> SQLite schema, data access, default roles, and demo records.',
'<b>access.py, security.py:</b> permission enforcement, routine and emergency access, audit logging, authentication, and encryption.',
'<b>validation.py, reports.py:</b> form validation, dashboard statistics, and CSV audit export.',
'<b>README.md, requirements.txt:</b> project documentation and dependency configuration.'
]:
    y=para(c,line,50,y-10,1000,small)
c.showPage();c.save()

for stem in ['MediVault-System-Screenshots-and-User-Guide','MediVault-Group-Contribution']:
    image_dir=ROOT/(stem+'-Images');image_dir.mkdir(exist_ok=True)
    pdf=pdfium.PdfDocument(str(ROOT/(stem+'.pdf')))
    for index,page in enumerate(pdf):
        page.render(scale=1.5).to_pil().save(image_dir/f'page-{index+1:02d}.png')
    with zipfile.ZipFile(ROOT/(stem+'-Images.zip'),'w',zipfile.ZIP_DEFLATED) as z:
        for p in image_dir.glob('*.png'): z.write(p,p.name)
with zipfile.ZipFile(ROOT/'MediVault-Original-Tab-Screenshots.zip','w',zipfile.ZIP_DEFLATED) as z:
    for p in (ROOT/'screenshots').glob('*.jpg'): z.write(p,p.name)
print('Created two PDFs, 14 page images, and screenshot archives.')
