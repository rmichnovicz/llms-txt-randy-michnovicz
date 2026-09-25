import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';
function fixture(...args:string[]) {return execFileSync(resolve('../.venv/bin/python'),[resolve('../tests/ui_fixture.py'),...args],{encoding:'utf8'});}
for(const width of [320,1280]) {
 test(`reader tests and revision comparison at ${width}px`, async ({page}) => {
  const {id,token}=JSON.parse(fixture('seed'));
  try {
   await page.setViewportSize({width,height:900});
   await page.goto(`/s/${id}#key=${token}`);
   await page.getByRole('button',{name:'Test this guide'}).click();
   await page.getByRole('button',{name:'Run suggested tests'}).click();
   const report=page.getByRole('article',{name:'Reader test results'});
   await expect(report).toContainText('queued');
   await expect(page.locator('.draft-badge')).toHaveText('Draft');
   fixture('evaluate',id);
   await expect(report).toContainText('Expected source cited');
   await expect(report).toContainText('Authenticate using an API key.');
   await report.getByText('Pages and steps',{exact:true}).click();
   await expect(report).toContainText('Read frozen source');
   expect((await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze()).violations).toEqual([]);
   await page.screenshot({path:`test-results/reader-test-${width}.png`,fullPage:true});
   await page.getByRole('button',{name:'Markdown',exact:true}).click();
   await page.getByLabel('Document Markdown').fill('# Acme\n\nThis document no longer has links.');
   await expect(page.getByRole('button',{name:'Run suggested tests'})).toBeDisabled();
   await page.getByRole('button',{name:'Save changes',exact:true}).click();
   await expect(report).toContainText('different version');
   await page.getByRole('button',{name:'Rerun same questions'}).click();
   await expect(report).toContainText('queued');
   fixture('evaluate',id);
   await expect(report).toContainText('Comparing with version');
   await expect(report).toContainText('Previous: Expected source cited → Now: Could not answer');
   await page.getByLabel('Or test a customer question').fill('Can I search my internal documents?');
   await page.getByRole('button',{name:'Test my question',exact:true}).click();
   await expect(report).toContainText('queued');
   fixture('fail',id);
   await expect(report.getByRole('alert')).toBeVisible();
   await page.getByRole('button',{name:'Rerun same questions'}).click();
   await expect(report).toContainText('queued');
   fixture('evaluate',id);
   await expect(report).toContainText('Could not answer');
   await page.reload();
   await page.getByRole('button',{name:'Test this guide'}).click();
   await expect(page.getByRole('article',{name:'Reader test results'})).toContainText('Could not answer');
   expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
   expect((await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze()).violations).toEqual([]);
  } finally {fixture('cleanup',id);}
 });
}
