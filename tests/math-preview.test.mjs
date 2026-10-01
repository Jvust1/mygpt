import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import katex from '../third_party/katex/katex.mjs';
import {canPreviewMath,MATH_LIMITS} from '../host/math-preview.js';

test('exact pinned KaTeX runtime and MIT license are present',async()=>{
  assert.equal(katex.version,'0.18.10');
  for(const [path,sha] of [['katex.mjs','694a531495903e374957e9a9c904a402e2f413762635df486c4cf6163320d1aa'],['LICENSE','766ccc1f306c885aa45542a9846bbd0a505b27a0374f146778171c2254ce18e3']])
    assert.equal(createHash('sha256').update(await readFile(new URL('../third_party/katex/'+path,import.meta.url))).digest('hex'),sha);
});
test('actual KaTeX emits native MathML fractions, roots, matrices and exact annotation',()=>{
  for(const [latex,tag] of [[String.raw`\frac{1}{2}`,'mfrac'],[String.raw`\sqrt{x^2+1}`,'msqrt'],[String.raw`\begin{pmatrix}1&2\\3&4\end{pmatrix}`,'mtable']]){
    assert(canPreviewMath(latex));
    const result=katex.renderToString(latex,{output:'mathml',trust:false,strict:'error',maxExpand:200,maxSize:10});
    assert(result.includes('<'+tag));assert(result.includes('application/x-tex'));assert(!result.includes('katex-html'));
  }
});
test('input budget is inclusive and programming/HTML commands fall back before parsing',()=>{
  assert(canPreviewMath('x'.repeat(MATH_LIMITS.characters)));
  for(const v of ['',null,42,'x'.repeat(1001),'{'.repeat(33)+'x'+'}'.repeat(33),String.raw`\def\a{\a}\a`,String.raw`\href{javascript:alert(1)}{x}`,String.raw`\htmlStyle{position:fixed}{x}`,String.raw`\includegraphics{https://invalid.example/x}`,String.raw`\csname def\endcsname`,String.raw`\de^^66\a{z}`, '\\alpha'.repeat(81),'{x','x}'])assert.equal(canPreviewMath(v),false,String(v));
  assert(canPreviewMath('{'.repeat(32)+'x'+'}'.repeat(32)));
});
test('source display uses DOM construction and is wired to actual host entrypoints',async()=>{
  const helper=await readFile(new URL('../host/math-preview.js',import.meta.url),'utf8');
  assert(!/innerHTML|insertAdjacentHTML|DOMParser/.test(helper));
  assert(helper.includes("output:'mathml'"));assert(helper.includes('trust:false'));
  for(const p of ['selection.js','brain.js','reader.js'])assert((await readFile(new URL('../host/'+p,import.meta.url),'utf8')).includes('renderSourceParts'));
});
