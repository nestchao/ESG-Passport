// Only locally bundled, fictional fixture content. Never call real ESG APIs.
// Values are from src/ai/synthetic_dataset (not any customer's Supabase data).
export const PUBLIC_DEMO_SAMPLES=Object.freeze([
 {
  id:'syn-elec-001',kind:'electricity',title:'Electricity bill',file:'electricity-itemised-001-clean.png',
  image:'/demo-assets/electricity-itemised-001.png',month:'2026-05',date:'2026-06-02',
  period:'1–31 May 2026',quantity:'2577',unit:'kWh',source:'TENAGA DEMO MERANTI',
  disclosure:'E1.2',metric:'Purchased electricity',isEstimated:false,
  question:'What was your purchased electricity usage and illustrative emissions in May 2026?',
  answer:'Purchased electricity: 2,577 kWh in May 2026. Illustrative location-based estimate: 1,906.98 kg CO₂e (2,577 × a sample factor of 0.740 kg CO₂e/kWh). The factor is for demonstration and must be replaced with an applicable verified factor.',
  caveat:'Illustrative emissions use a sample factor, not an independently verified Malaysia grid factor.',
  suggestion:null
 },
 {
  id:'syn-water-001',kind:'water',title:'Water consumption bill',file:'water-sidebar-001-clean.png',
  image:'/demo-assets/water-sidebar-001.png',month:'2026-03',date:'2026-04-02',
  period:'1–31 March 2026',quantity:'807',unit:'m³',source:'AIR DEMO KENCANA',
  disclosure:'E2.1',metric:'Water consumed',isEstimated:true,
  question:'How much water was consumed in March 2026?',
  answer:'The sample water bill records 807 m³ of water consumption for March 2026. The source marks the reading as estimated, so this should be disclosed as an estimate, not presented as an actual meter reading.',
  caveat:'The source meter reading is estimated; confirm or disclose this limitation.',
  suggestion:null
 },
 {
  id:'syn-waste-001',kind:'waste',title:'Weighbridge transfer ticket',file:'waste-landscape-001-clean.png',
  image:'/demo-assets/waste-landscape-001.png',month:'2026-03',date:'2026-03-29',
  period:'29 March 2026',quantity:'4850',unit:'kg',source:'PUSAT TIMBANG DEMO MERANTI',
  disclosure:'E4.1',metric:'Unclassified waste transfer',isEstimated:false,
  question:'How much waste was diverted or disposed of in March 2026?',
  answer:'The sample weighbridge ticket reports a net TRANSFER weight of 4,850 kg on 29 March 2026 (gross 13,680 kg minus tare 8,830 kg). It declares a recycling destination, but does not independently establish that the material was recycled, generated, or disposed of. ESG treatment category remains unverified.',
  caveat:'Declared recycling destination does not prove waste diversion. No generated, diverted or disposed total can be verified from this ticket alone.',
  suggestion:{category:'waste_diverted',label:'Waste diverted',basis:'Ticket states “Tujuan: RECYCLING”',confidence:'Low · unverified'}
 }
]);
export const PUBLIC_DEMO_MONTHS=['2026-03','2026-05'];
export function demoSamplesForMonth(month){return PUBLIC_DEMO_SAMPLES.filter(sample=>sample.month===month);}
