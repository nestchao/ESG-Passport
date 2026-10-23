"""Eight original fictional Malaysian-style layouts; no external assets or network."""
from decimal import Decimal, ROUND_HALF_UP
from PIL import Image, ImageDraw, ImageFont
from .render import Page, CONTEXT, money, dm, font_path

def base_electricity(index):
    p=Page(620,1450,'electricity',index)
    usage=1746+index*307
    previous=38140+index*930
    current=previous+usage
    quantities=[200,100,usage-300]
    rates=[Decimal('.2200'),Decimal('.3400'),Decimal('.4300')]
    charges=[money(Decimal(q)*r) for q,r in zip(quantities,rates)]
    energy=sum(charges)
    service=Decimal('12.00')
    adjustment=Decimal('-3.20')
    subtotal=energy+service+adjustment
    outstanding=Decimal('28.40')
    total=subtotal+outstanding
    p.rect([20,20,600,66],fill='#d2dfe9')
    p.text('BIL ELEKTRIK DEMO',30,32,24,True)
    p.text('KENCANA DEMO ENERGY',30,80,19,True)
    p.text('SYNTHETIC / REKAAN',585,82,14,True,True)
    for y,t in [(112,'KILANG REKAAN ANGSANA'),(137,'LOT DEMO, JALAN CONTOH'),(162,'MALAYSIA - FICTIONAL PREMISE')]:p.text(t,30,y,15)
    for y,t in [(112,f'Account: DEMO-E-{index+1:04}'),(137,'Bill date: 02/10/2026'),(162,f'Invoice: DEMO-{index+1:05}')]:p.text(t,585,y,15,right=True)
    p.rect([20,204,600,252],fill='#f0e3da')
    p.text('JUMLAH PERLU DIBAYAR',30,219,17,True)
    p.text(f'RM {total:,.2f}',585,216,22,True,True,key='amount_due',value=str(total),unit='MYR')
    for n,(label,val) in enumerate([('Baki terdahulu / Outstanding',outstanding),('Caj semasa / Current charges',subtotal),('Bayaran diterima / Payments',Decimal('0.00'))]):
        y=266+n*31
        p.rect([20,y-3,600,y+26],fill='#e8edf4' if n%2==0 else '#f1f3f7')
        p.text(label,30,y+3,15)
        p.text(f'RM {val:,.2f}',585,y+3,16,right=True)
    p.text('TEMPOH BIL: 01/09/2026 - 30/09/2026',30,378,17,True)
    p.text('Jenis bacaan: Sebenar / Actual',30,410,15)
    p.text('Tariff: DEMO COMMERCIAL',585,410,15,right=True)
    p.rect([20,449,600,483],fill='#d5deed')
    for x,t in [(30,'Blok / Band'),(237,'kWh'),(345,'RM/kWh'),(494,'RM')]:p.text(t,x,460,15,True)
    for n,(q,r,c) in enumerate(zip(quantities,rates,charges)):
        y=493+n*37
        p.rect([20,y-3,600,y+31],fill='#edf0f6' if n%2==0 else '#e0e7f2')
        for x,t in [(30,['First / Pertama','Next / Seterusnya','Remaining / Baki'][n]),(237,f'{q:,}'),(345,f'{r:.4f}')]:p.text(t,x,y+4,15)
        p.text(f'{c:.2f}',585,y+4,16,right=True)
    p.rule(20,615,600)
    p.text('TOTAL ENERGY / JUMLAH TENAGA',30,634,16,True)
    p.text(f'{usage:,} kWh',585,630,23,True,True,key='purchased_electricity',value=str(usage),unit='kWh',role='activity')
    p.rect([20,688,600,724],fill='#d5deed')
    for x,t in [(30,'Keterangan / Description'),(365,'Unit'),(505,'RM')]:p.text(t,x,701,15,True)
    detail=[('Energy / Tenaga','kWh',energy),('Service charge / Perkhidmatan','-',service),('Adjustment / Pelarasan','-',adjustment)]
    for n,(label,unit,amount) in enumerate(detail):
        y=735+n*39
        p.rect([20,y-3,600,y+33],fill='#edf0f6' if n%2==0 else '#e0e7f2')
        p.text(label,30,y+5,15)
        p.text(unit,365,y+5,15)
        p.text(f'{amount:,.2f}',585,y+5,16,right=True)
    p.text('CAJ SEMASA / CURRENT CHARGES',30,870,16,True)
    p.text(f'RM {subtotal:,.2f}',585,867,22,True,True)
    p.text(f'Maximum demand: {24+index*3}.00 kW',30,919,15,key='maximum_demand',value=str(24+index*3),unit='kW')
    p.text('Power factor: 0.96',585,919,15,right=True)
    p.rect([20,965,600,1000],fill='#d5deed')
    p.text('MAKLUMAT METER / METER INFORMATION',30,978,15,True)
    for x,t in [(30,'Meter'),(220,'Previous'),(363,'Current'),(510,'Factor')]:p.text(t,x,1020,14,True)
    p.text(f'DEMO-M-{index+1:03}',30,1052,15)
    p.text(f'{previous:,}',220,1052,17,key='electricity_previous_reading',value=str(previous),unit='kWh')
    p.text(f'{current:,}',363,1052,17,key='electricity_current_reading',value=str(current),unit='kWh')
    p.text('1.000',510,1052,16)
    p.text('Usage = (current - previous) x factor',30,1090,14)
    p.text('Illustrative rates, not current official tariffs.',30,1130,14)
    p.barcode(35,1184,550,52)
    p.text(f'DEMO BILL REFERENCE E-{index+1:04}',30,1254,15)
    p.text('NOT VALID FOR PAYMENT',30,1300,17,True)
    p.text('All details and values are fictional.',30,1340,14)
    p.text('For synthetic OCR and key-value testing only.',30,1374,14)
    p.checks=[{'equation':'current - previous = kWh','lhs':current-previous,'rhs':usage},
              {'equation':'sum(band quantities) = usage','lhs':sum(quantities),'rhs':usage},
              {'equation':'energy + service + adjustment + outstanding = due','lhs':str(sum(charges)+service+adjustment+outstanding),'rhs':str(total)}]
    return p

def legacy_electricity(index):
    p=base_electricity(index)
    # Add small-print information in actual empty gaps, without covering existing fields.
    p.text('Reading dates: 01/09/2026 -> 30/09/2026',30,434,11)
    p.text('Pay before: 01/11/2026',585,389,12,right=True)
    p.text('kW measures demand; kWh measures energy.',30,946,11)
    p.text('Demo service channel: DEMO ONLY / Saluran contoh',30,1150,11)
    p.text('Please retain this statement / Sila simpan penyata ini',30,1167,11)
    p.text('Amounts are illustrative; all account identifiers are fictional.',30,1397,11)
    # Transcript order follows page position, including added notices.
    p.lines.sort(key=lambda line:(line['bbox'][1],line['bbox'][0]))
    return p

def extend(page,height):
    paper=Image.new('RGB',(page.w*2,height*2),'#fffefa');paper.paste(page.paper,(0,0))
    ink=Image.new('L',paper.size,0);ink.paste(page.ink,(0,0))
    page.paper,page.ink,page.h=paper,ink,height
    page.bg,page.pen=ImageDraw.Draw(paper),ImageDraw.Draw(ink)

def electricity_stub(index):
    p=legacy_electricity(index)
    extend(p,1660)
    for x in range(24,600,12):p.bg.line((x*2,1450*2,(x+6)*2,1450*2),fill='#999999',width=2)
    p.text('KERATAN BAYARAN / PAYMENT SLIP',30,1470,16,True)
    due=next(f['value'] for f in p.fields if f['field']=='amount_due')
    p.text(f'Akaun: DEMO-E-{index+1:04}',30,1507,15)
    p.text(f'RM {due}',585,1507,20,True,True)
    p.barcode(30,1550,365,35)
    p.text('REKAAN - TIDAK BOLEH DIBAYAR',30,1610,13,True)
    return p

def electricity_itemised(index):
    p=Page(760,1350,'electricity',index)
    usage=2184+index*393;prev=48136+index*1480;current=prev+usage
    rates=[Decimal('.2710'),Decimal('.0480'),Decimal('.1320')]
    amounts=[money(Decimal(usage)*r) for r in rates]
    retail=Decimal('10.00');currentbill=sum(amounts)+retail
    balance=Decimal('24.70');due=currentbill+balance
    p.rect([22,22,738,84],fill='#deebf0')
    p.text('TENAGA DEMO MERANTI',35,35,27,True)
    p.text('BIL ELEKTRIK / REKAAN',35,72,13,True)
    p.text('KEDAI REKAAN MERANTI',35,117,19,True)
    p.text('LOT DEMO 12, JALAN REKAAN',35,147,15)
    p.text('00000 BANDAR REKAAN, MALAYSIA',35,171,14)
    p.text(f'No. Akaun: DEMO-ME-{index+1:04}',724,118,17,True,True)
    p.text('Tarikh Bil: 02/10/2026',724,151,16,right=True)
    p.text('Tarikh Akhir: 01/11/2026',724,179,15,right=True)
    p.rect([28,226,733,311],fill='#f0e7df')
    p.text('JUMLAH BIL ANDA',43,241,17,True)
    p.text(f'RM {due:,.2f}',713,240,29,True,True,key='amount_due',value=str(due),unit='MYR')
    p.text(f'Baki terdahulu RM {balance:.2f}  +  Caj semasa RM {currentbill:.2f}',43,282,15)
    p.text('Tempoh Bil: 01/09/2026 - 30/09/2026 (30 hari)',35,337,17,True)
    p.text('Ringkasan Penggunaan Anda',35,377,20,True)
    p.text(f'{usage:,} kWh',721,371,29,True,True,key='purchased_electricity',value=str(usage),unit='kWh',role='activity')
    p.rect([28,427,733,465],fill='#e1e9ee')
    for x,t in [(40,'No. Meter'),(257,'Dahulu'),(426,'Semasa'),(604,'Pengganda')]:p.text(t,x,441,15,True)
    p.text(f'DEMO-M-{index+1:03}',40,485,16)
    p.text(f'{prev:,}',257,485,19,key='electricity_previous_reading',value=str(prev),unit='kWh')
    p.text(f'{current:,}',426,485,19,key='electricity_current_reading',value=str(current),unit='kWh')
    p.text('1.000',604,485,17)
    p.text('Jenis bacaan: Sebenar',40,524,15)
    p.rect([28,566,733,604],fill='#dfe8ee')
    for x,t in [(40,'Jenis Caj'),(344,'Kuantiti'),(485,'Kadar RM'),(652,'RM')]:p.text(t,x,580,15,True)
    rows=[('Tenaga',f'{usage:,} kWh',rates[0],amounts[0]),('Kapasiti',f'{usage:,} kWh',rates[1],amounts[1]),
          ('Rangkaian',f'{usage:,} kWh',rates[2],amounts[2]),('Peruncitan','1 bulan',None,retail),
          ('Pelarasan bahan api','-',None,Decimal('0.00'))]
    for n,(label,qty,rate,amount) in enumerate(rows):
        y=620+n*46
        p.rect([28,y-3,733,y+35],fill='#f0f3f5' if n%2==0 else '#e7edf1')
        p.text(label,40,y+6,17)
        p.text(qty,344,y+6,16)
        p.text(f'{rate:.4f}' if rate else '-',485,y+6,16)
        p.text(f'{amount:,.2f}',715,y+6,17,right=True)
    p.text('CAJ SEMASA',40,872,19,True)
    p.text(f'RM {currentbill:,.2f}',715,869,25,True,True)
    p.rule(28,920,733)
    p.text('Maklumat penggunaan terdahulu (kWh)',40,943,16,True)
    for n,(label,value) in enumerate([('JUL 2026',1756+index*201),('OGO 2026',2010+index*190)]):
        x=40+n*250
        p.text(label,x,981,15)
        p.text(f'{value:,} kWh',x,1010,20,True)
    p.text('Kadar ilustrasi, bukan tarif rasmi. Tiada bayaran diperlukan.',40,1072,14)
    p.barcode(40,1120,565,45)
    p.text('RUJUKAN DEMO SAHAJA',40,1186,14)
    p.text('SYNTHETIC - NOT A REAL BUSINESS RECORD',40,1240,16,True)
    p.text('Semua butiran adalah rekaan. Untuk ujian OCR sahaja.',40,1280,14)
    p.checks=[{'equation':'current - previous = usage','lhs':current-prev,'rhs':usage},
              {'equation':'component charges + retail + balance = due','lhs':str(sum(amounts)+retail+balance),'rhs':str(due)}]
    return p

def water_compact(index):
    p=Page(640,1020,'water',index)
    prev=9126+index*580;usage=74+index*35;current=prev+usage
    a=money(Decimal(20)*Decimal('1.10'));b=money(Decimal(usage-20)*Decimal('1.65'))
    bill=a+b;arrears=Decimal('8.40');due=bill+arrears
    p.text('AIR DEMO ANGSANA',27,27,25,True)
    p.text('BIL AIR',612,29,25,True,True)
    p.text('PERKHIDMATAN BEKALAN AIR',27,66,14)
    p.text('REKAAN / SYNTHETIC',612,71,12,True,True)
    p.text('KEDAI REKAAN MERANTI',27,116,18,True)
    p.text('LOT DEMO 12, JALAN REKAAN',27,145,14)
    p.text('00000 BANDAR REKAAN, MALAYSIA',27,171,13)
    for y,t in [(115,f'Bil: DEMO-W-{index+1:04}'),(145,'Tarikh: 02/10/2026'),(173,'Jenis: Perniagaan')]:p.text(t,610,y,14,right=True)
    p.text(f'No. Akaun: DEMO-AIR-{index+1:04}',27,218,16,True)
    p.text('No. Meter: DEMO-WM-01',610,218,14,right=True)
    p.rect([23,264,616,303],fill='#dce9e5')
    for x,t in [(34,'Tarikh Bacaan'),(259,'Bacaan m3'),(455,'Penggunaan')]:p.text(t,x,279,15,True)
    for y,date,value,key in [(323,'01/09/2026',prev,'water_previous_reading'),(365,'30/09/2026',current,'water_current_reading')]:
        p.text(date,34,y,16)
        p.text(f'{value:,}',259,y,18,key=key,value=str(value),unit='m3')
    p.text(f'{usage} m3',600,345,25,True,True,key='water_consumption',value=str(usage),unit='m3',role='activity')
    p.rect([23,410,616,449],fill='#edf2f0')
    p.text('TEMPOH: 01/09/2026 - 30/09/2026',34,425,15,True)
    p.text('Bacaan: E / Anggaran' if index else 'Bacaan: N / Sebenar',34,473,15,
           key='reading_type',value='estimated' if index else 'actual')
    p.rect([23,516,616,555],fill='#dce9e5')
    for x,t in [(34,'Blok'),(209,'m3'),(335,'Kadar RM'),(514,'Amaun RM')]:p.text(t,x,531,14,True)
    for y,label,q,rate,val in [(579,'Pertama',20,'1.10',a),(625,'Seterusnya',usage-20,'1.65',b)]:
        for x,t in [(34,label),(209,str(q)),(335,rate)]:p.text(t,x,y,16)
        p.text(f'{val:.2f}',600,y,17,right=True)
    p.rule(25,666,616)
    for y,label,val,bold in [(693,'Bil semasa',bill,False),(734,'Tunggakan',arrears,False),(783,'JUMLAH BAYARAN',due,True)]:
        p.text(label,34,y,17,bold)
        p.text(f'RM {val:.2f}',600,y,22 if bold else 18,bold,True,
                   key='amount_due' if bold else None,value=str(val),unit='MYR')
    p.text('Bayar sebelum: 01/11/2026 (contoh sahaja)',34,839,14)
    p.text('Kadar rekaan untuk ujian, bukan tarif rasmi.',34,868,13)
    p.barcode(34,907,352,35)
    p.text('REKAAN - TIDAK SAH UNTUK PEMBAYARAN',34,973,14,True)
    p.checks=[{'equation':'current - previous = consumption','lhs':current-prev,'rhs':usage},
              {'equation':'band charges + arrears = due','lhs':str(a+b+arrears),'rhs':str(due)}]
    return p

def sidebar_water(index):
    p=Page(700,1240,'water',index)
    prev=8640+index*460
    usage=93+index*34
    curr=prev+usage
    first=money(Decimal('20')*Decimal('1.10'))
    rest=money(Decimal(usage-20)*Decimal('1.65'))
    bill=first+rest
    opening=Decimal('32.00');paid=Decimal('20.00');balance=opening-paid
    total=bill+balance
    p.text('AIR DEMO KENCANA',25,24,23,True)
    p.text('BEKALAN AIR / WATER SERVICES',25,59,13)
    p.text('BIL AIR',675,29,28,True,True)
    p.text('SYNTHETIC / REKAAN',675,68,12,True,True)
    p.text('KEDAI REKAAN ANGSANA',25,105,17,True)
    p.text('LOT DEMO, JALAN CONTOH',25,133,14)
    p.text('MALAYSIA - FICTIONAL PREMISE',25,157,13)
    p.text(f'Account / Akaun: DEMO-W-{index+1:04}',25,192,16,True)
    p.text('No. meter: DEMO-WM-001',25,222,14)
    p.barcode(26,259,190,36)
    p.barcode(291,259,150,36)
    p.text('DEMO REFERENCE ONLY',25,309,11)
    p.rect([484,105,679,1160],fill='#edf5f3',outline='#b8cfc9')
    side=[(123,'NO. AKAUN / ACCOUNT',13,True),(150,f'DEMO-W-{index+1:04}',18,True),
          (199,'TARIKH BIL',13,True),(224,'02/10/2026',17,False),
          (268,'BAYAR SEBELUM',13,True),(293,'01/11/2026',17,False),
          (339,'Jenis: DEMO NIAGA',13,False)]
    for y,t,size,bold in side:p.text(t,496,y,size,bold)
    p.rect([492,386,671,446],fill='#c8e3a7')
    p.text('JUMLAH PERLU BAYAR',500,397,12,True)
    p.text(f'RM {total:.2f}',500,419,21,True,key='amount_due',value=str(total),unit='MYR')
    p.text('CURRENT CHARGES',496,480,13,True)
    p.text(f'RM {bill:.2f}',496,507,21,True)
    p.text('OUTSTANDING',496,556,13,True)
    p.text(f'RM {balance:.2f}',496,583,19,True)
    for y,t in [(640,'Payment reference'),(667,f'DEMO-PAY-{index+1:04}'),(720,'DEMO CHANNELS'),
                (749,'Counter / Kaunter'),(775,'Online / Dalam talian'),(802,'Reference only'),(849,'NOT PAYABLE')]:
        p.text(t,496,y,12,y in [720,849])
    p.barcode(497,904,162,45)
    p.text('Retain this bill.',496,985,12)
    p.text('Sila simpan bil ini.',496,1008,12)
    p.text('All values fictional.',496,1096,11)
    p.rect([22,348,463,380],fill='#dfe8e6')
    p.text('RINGKASAN AKAUN / ACCOUNT SUMMARY',30,359,14,True)
    rows=[('Baki terdahulu / Previous',opening),('Bayaran diterima / Payment',paid),
          ('Baki belum bayar / Outstanding',balance),('Caj semasa / Current bill',bill),('Jumlah / Total due',total)]
    for n,(label,value) in enumerate(rows):
        y=393+n*32
        p.rule(24,y+27,462)
        p.text(label,30,y+4,13,n==4)
        p.text(f'{value:.2f}',451,y+4,15,n==4,True)
    p.text('TEMPOH: 01/09/2026 - 30/09/2026',25,588,15,True)
    p.rect([22,625,463,658],fill='#dcebea')
    p.text('BUTIRAN METER / METER DETAILS',30,638,14,True)
    for x,t in [(30,'Bacaan'),(231,'Tarikh'),(346,'m3')]:p.text(t,x,680,13,True)
    for y,label,date,value,key in [(712,'Dahulu / Previous','01/09/2026',prev,'water_previous_reading'),
                                   (753,'Semasa / Current','30/09/2026',curr,'water_current_reading')]:
        p.text(label,30,y,13)
        p.text(date,231,y,13)
        p.text(f'{value:,}',452,y,16,False,True,key=key,value=str(value),unit='m3')
    p.rule(24,790,463)
    p.text('Penggunaan / Usage',30,811,15,True)
    p.text(f'{usage} m3',452,808,23,True,True,key='water_consumption',value=str(usage),unit='m3',role='activity')
    p.text('Jenis: E (Anggaran)' if index else 'Jenis: N (Sebenar)',30,851,13,
           key='reading_type',value='estimated' if index else 'actual')
    p.rect([22,893,463,925],fill='#dcebea')
    for x,t in [(30,'Blok'),(169,'m3'),(258,'RM/m3'),(397,'RM')]:p.text(t,x,905,13,True)
    for y,label,q,rate,value in [(947,'Pertama',20,'1.10',first),(981,'Baki',usage-20,'1.65',rest)]:
        for x,t in [(30,label),(169,str(q)),(258,rate)]:p.text(t,x,y,14)
        p.text(f'{value:.2f}',452,y,15,right=True)
    p.rule(24,1016,463)
    p.text('JUMLAH SEMASA',30,1035,15,True)
    p.text(f'RM {bill:.2f}',452,1032,20,True,True)
    p.text('m3 = meter padu / cubic metres',25,1084,12)
    p.text('Illustrative bands, not official tariffs.',25,1112,12)
    p.text('NOT VALID FOR PAYMENT - FICTIONAL OCR FIXTURE',25,1179,13,True)
    p.text('No real names, addresses, accounts or bill values.',25,1209,12)
    p.lines.sort(key=lambda line:(line['bbox'][1],line['bbox'][0]))
    p.checks=[{'equation':'current - previous = usage m3','lhs':curr-prev,'rhs':usage},
              {'equation':'charges + opening - paid = total','lhs':str(first+rest+opening-paid),'rhs':str(total)}]
    return p

def water_stub(index):
    p=water_compact(index)
    extend(p,1450)
    p.rule(24,1035,616)
    p.text('KERATAN BAYARAN / PAYMENT STUB',28,1060,17,True)
    p.text('AIR DEMO ANGSANA - REKAAN',28,1100,17,True)
    p.text(f'No. Akaun: DEMO-AIR-{index+1:04}',28,1145,16)
    due=next(f['value'] for f in p.fields if f['field']=='amount_due')
    p.text(f'Jumlah RM {due}',610,1145,19,True,True)
    p.barcode(38,1200,540,60)
    p.text(CONTEXT['business'],28,1295,17)
    p.text('LOT DEMO, JALAN REKAAN, MALAYSIA',28,1330,14)
    p.text('REKAAN - TIDAK BOLEH DIBAYAR',28,1390,15,True)
    return p

def fuel_receipt(index,subsidised=False):
    rng=CONTEXT['rng'];p=Page(600,1260 if subsidised else 1050,'fuel',index)
    litres=Decimal(rng.randrange(5000,80000))/1000
    product='RON95' if subsidised else rng.choice(['RON95','DIESEL','RON97'])
    posted=Decimal(rng.choice(['2.40','2.65','3.05','3.25']))
    gross=money(litres*posted)
    discount=money(litres*Decimal('0.55')) if subsidised else Decimal('0.00')
    net=gross-discount
    rounded=(net/Decimal('.05')).quantize(Decimal(1),rounding=ROUND_HALF_UP)*Decimal('.05')
    cash=(rounded/Decimal(50)).to_integral_value(rounding='ROUND_CEILING')*50
    if cash==0:cash=Decimal(50)
    payment=rng.choice(['CASH / TUNAI','DEMO WALLET','DEMO CARD'])
    def text(t,y,size=18,bold=False,key=None,value=None,unit=None,right=False):
        return p.text(t,570 if right else 30,y,size,bold,right,key,value,unit,
             'activity' if key and key.endswith('consumption') else 'context',mono=True)
    text('STESEN MINYAK DEMO',26,25,True)
    text('MERANTI DEMO NIAGA',65,20,True)
    text('LOT DEMO, JALAN REKAAN',105,17)
    text('MALAYSIA - SEMUA DATA REKAAN',135,17)
    text('FINAL RECEIPT / RESIT AKHIR',183,21,True)
    text(f'No: DEMO-F-{index+1:05}',226)
    text(f'Date: {dm(CONTEXT["transaction"])}  {rng.randrange(7,22):02}:34',258)
    text(f'Pump: {rng.randrange(1,13):02}     Cashier: DEMO',290)
    p.rule(26,330,574)
    text(f'PRODUCT: {product}',350,22,True)
    key='diesel_consumption' if product=='DIESEL' else 'petrol_consumption'
    text(f'Volume: {litres:.3f} L',395,21,key=key,value=str(litres),unit='L')
    text(f'Price/L: RM {posted:.2f}',435,20,key='fuel_unit_price',value=str(posted),unit='MYR/L')
    text(f'Fuel amount: RM {gross:.2f}',475,20,key='fuel_amount',value=str(gross),unit='MYR')
    y=530
    if subsidised:
        p.rect([25,520,575,740],outline='#888888')
        text('SUBSIDI DEMO / ILLUSTRATION',540,18,True)
        text(f'Market price     RM {posted:.2f}/L',580,18)
        text(f'Demo reduction   RM 0.55/L',615,18)
        text(f'Subsidy amount   RM {discount:.2f}',650,18)
        text('Not an eligibility or quota record.',695,15)
        y=780
    text(f'Subtotal     RM {net:.2f}',y,20,right=True)
    text(f'Rounding     RM {rounded-net:+.2f}',y+40,18,right=True)
    text(f'GRAND TOTAL  RM {rounded:.2f}',y+80,22,True,key='rounded_total',value=str(rounded),unit='MYR',right=True)
    text('Payment: '+payment,y+130,18)
    if payment=='CASH / TUNAI':
        text(f'Cash         RM {cash:.2f}',y+166,18,key='cash_paid',value=str(cash),unit='MYR',right=True)
        text(f'Change       RM {cash-rounded:.2f}',y+201,18,key='change',value=str(cash-rounded),unit='MYR',right=True)
    else:text(f'Amount paid  RM {rounded:.2f}',y+166,18,right=True)
    text('REKAAN / SYNTHETIC - NOT PAYABLE',p.h-90,16,True)
    text('Prices illustrative, not official.',p.h-55,15)
    p.checks=[{'equation':'litres * posted price = gross','lhs':str(money(litres*posted)),'rhs':str(gross)},
        {'equation':'gross - demo subsidy = subtotal','lhs':str(gross-discount),'rhs':str(net)}]
    p.supporting_fields={'demo_subsidy_amount':str(discount),'subtotal':str(net),'payment_method':payment,
        'rounding_adjustment':str(rounded-net),'gross_vs_net_policy':'fuel_amount is gross product amount; rounded_total is payable after illustrative subsidy and rounding'}
    return p

def landscape_waste(index):
    rng=CONTEXT['rng'];p=Page(1080,740,'waste',index)
    tare=rng.randrange(3200,10000,10);net=rng.randrange(200,9500,10);gross=tare+net
    rate=Decimal(rng.randrange(55,120));charge=money(Decimal(net)/1000*rate)
    p.text('PUSAT TIMBANG DEMO MERANTI',30,28,26,True,mono=True)
    p.text('SLIP TIMBANG SISA / WASTE WEIGHBRIDGE',30,70,19,mono=True)
    p.text('LOT DEMO, JALAN REKAAN, MALAYSIA',30,105,16,mono=True)
    p.text('REKAAN / SYNTHETIC',1045,30,17,True,True,mono=True)
    p.text(f'Tarikh: {dm(CONTEXT["transaction"])}',30,165,18,mono=True)
    p.text(f'Tiket: DEMO-W-{index+1:05}',730,165,18,mono=True)
    p.text(CONTEXT['business'],30,205,18,mono=True)
    p.text('Kenderaan: DEMO-TRUCK',730,205,17,mono=True)
    material=CONTEXT['material']
    p.text('Bahan: '+material,30,247,18,mono=True)
    p.text('Tujuan: '+CONTEXT['route'].upper(),30,287,18,key='treatment_route',
           value=CONTEXT['route'],mono=True)
    p.rule(28,335,1045)
    for y,label,val,key in [(365,'GROSS / BERAT KASAR',gross,'gross_weight'),
                           (413,'TARE / BERAT KENDERAAN',tare,'tare_weight'),
                           (466,'NET / BERAT BERSIH',net,'waste_transferred')]:
        p.text(label,40,y,22,key=='waste_transferred',mono=True)
        p.text(f'{val:,} kg',700,y,23,key=='waste_transferred',key=key,value=str(val),unit='kg',
            role='activity' if key=='waste_transferred' else 'context',mono=True)
    p.text(f'Price/tonne: RM {rate:.2f}',40,535,18,key='waste_unit_price',value=str(rate),unit='MYR/t',mono=True)
    p.text(f'Amount: RM {charge:.2f}',700,535,20,True,key='waste_charge',value=str(charge),unit='MYR',mono=True)
    p.rule(28,590,1045)
    p.text('Operator: DEMO        Received by: DEMO',40,615,17,mono=True)
    p.text('Declared route only; not proof of completed disposal or recovery.',40,657,16)
    p.text('All weights fictional. Not a scheduled-waste consignment note.',40,697,16)
    p.checks=[{'equation':'gross - tare = net','lhs':gross-tare,'rhs':net},
              {'equation':'net / 1000 * rate = amount','lhs':str(money(Decimal(net)/1000*rate)),'rhs':str(charge)}]
    return p

def thermal_waste(index):
    p=Page(560,990,'waste',index)
    tare=4260+index*260
    net=1820+index*320
    gross=tare+net
    rate=Decimal('78.00')
    amount=money(Decimal(net)/1000*rate)
    p.period={'start':'2026-09-22','end':'2026-09-22'}
    for y,t,size,bold in [(25,'KENCANA DEMO RECOVERY',24,True),(61,'WEIGHBRIDGE / SLIP TIMBANG',18,False),
                         (91,'LOT DEMO, JALAN CONTOH',18,False),(120,'MALAYSIA - FICTIONAL SITE',17,False),
                         (158,'SYNTHETIC / REKAAN',17,True)]:
        # Centered receipt header, narrow mono typography.
        width=p.pen.textlength(t,font=ImageFont.truetype(str(font_path(True, bold)),size*2))/2
        p.text(t,(p.w-width)/2,y,size,bold,mono=True)
    p.text(f'Ticket: DEMO-WT-{index+1:04}',28,222,18,mono=True)
    p.text('22/09/2026',530,222,18,right=True,mono=True)
    context=[('Vehicle','DEMO-TRUCK-01'),('Customer','ANGSANA DEMO'),('Area','DEMO INDUSTRIAL'),
             ('Waste','CARDBOARD' if index else 'GENERAL WASTE'),('Route','RECYCLING' if index else 'LANDFILL'),
             ('Carrier','DEMO LOGISTICS'),('Time in','10:14'),('Time out','10:39')]
    for n,(label,value) in enumerate(context):
        y=279+n*37
        p.text(label,30,y,19,mono=True)
        p.text(': '+value,217,y,19,key='treatment_route' if label=='Route' else None,
               value=('recycling' if index else 'landfill') if label=='Route' else None,mono=True)
    for y,label,value,key in [(610,'1st/Gross',gross,'gross_weight'),(653,'2nd/Tare',tare,'tare_weight'),(701,'Net weight',net,'waste_transferred')]:
        p.text(label,30,y,20,y==701,mono=True)
        p.text(f': {value:,} kg',217,y,20,y==701,key=key,value=str(value),unit='kg',
               role='activity' if key=='waste_transferred' else 'context',mono=True)
    p.text('Price/tonne',30,758,19,mono=True)
    p.text(f': RM {rate:.2f}',217,758,19,key='waste_unit_price',value=str(rate),unit='MYR/t',mono=True)
    p.text('Amount',30,798,19,mono=True)
    p.text(f': RM {amount:.2f}',217,798,19,key='waste_charge',value=str(amount),unit='MYR',mono=True)
    p.text('Operator: DEMO',30,861,17,mono=True)
    p.text('NOT AN OFFICIAL WASTE RECORD',30,911,16,True,mono=True)
    p.text('All weights and details fictional.',30,945,15,mono=True)
    p.checks=[{'equation':'gross - tare = net','lhs':gross-tare,'rhs':net},
              {'equation':'net kg / 1000 * price per tonne = amount','lhs':str(money(Decimal(net)/1000*rate)),'rhs':str(amount)}]
    return p
