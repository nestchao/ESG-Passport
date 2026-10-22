import {test} from 'node:test';
import assert from 'node:assert/strict';
import {replaceDeclaration} from './declaration-updates.mjs';
test('server-confirmed declaration replaces the matching month/code immediately without losing other declarations',()=>{const old=[{code:'G1.1',period:'2026-09',version:1,answer:{directors:2}},{code:'S1.1',period:'2026-09',version:1}];const saved={code:'G1.1',period:'2026-09',version:2,answer:{directors:3}};const next=replaceDeclaration(old,saved);assert.deepEqual(next,[saved,old[1]]);assert.equal(old[0].answer.directors,2);assert.deepEqual(replaceDeclaration(next,old[0]),next);});
