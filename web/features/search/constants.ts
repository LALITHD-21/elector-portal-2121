import { SearchFacets } from './types';

export const VERIFIED_FACETS: SearchFacets = {
  districts: ['Chikkaballapura', 'Chitradurga', 'Davanagere', 'Kolar', 'Tumkur'],
  taluks: [
    'Bagepalli', 'Bangarapet', 'Challakere', 'Channagiri', 'Chikkaballapur',
    'Chikkanayakanahalli', 'Chintamani', 'Chitradurga', 'Davanagere', 'Gauribidanur',
    'Gubbi', 'Harihara', 'Hiriyur', 'Holalkere', 'Honnali', 'Hosadurga',
    'Jagalur', 'KGF', 'Kolar', 'Koratagere', 'Kunigal', 'Madhugiri', 'Malur',
    'Molakalmuru', 'Mulbagal', 'Pavagada', 'Shidlaghatta', 'Sira', 'Srinivaspur',
    'Tiptur', 'Tumkur City', 'Tumkur Rural', 'Turuvekere'
  ],
  acs: [
    'Bagepalli', 'Bangarapet', 'Challakere', 'Chikkaballapur', 'Chintamani',
    'Chitradurga', 'Davanagere North', 'Davanagere South', 'Gauribidanur',
    'Harihar', 'Hiriyur', 'Hosadurga', 'KGF', 'Kolar', 'Madhugiri',
    'Malur', 'Pavagada', 'Sidlaghatta', 'Sira', 'Srinivaspur', 'Tumkur City', 'Tumkur Rural'
  ],
  parts: Array.from({ length: 151 }, (_, i) => String(i + 1)),
  districtAcs: {
    Tumkur: ['Tumkur City', 'Tumkur Rural', 'Madhugiri', 'Sira', 'Pavagada'],
    Chitradurga: ['Chitradurga', 'Challakere', 'Hiriyur', 'Hosadurga'],
    Kolar: ['Kolar', 'KGF', 'Bangarapet', 'Malur', 'Srinivaspur'],
    Davanagere: ['Davanagere North', 'Davanagere South', 'Harihar'],
    Chikkaballapura: ['Chikkaballapur', 'Gauribidanur', 'Bagepalli', 'Sidlaghatta', 'Chintamani'],
  },
};
