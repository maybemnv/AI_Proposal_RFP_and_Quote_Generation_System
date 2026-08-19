import {expect, test as base} from "@playwright/test";

export const test = base.extend<{resetFixture: void}>({
  resetFixture: [async ({request}, use) => {
    const response = await request.post("http://localhost:8106/v1/fixture/reset");
    if (!response.ok()) {
      throw new Error(`fixture reset failed: ${response.status()} ${await response.text()}`);
    }
    await use();
  }, {auto: true}],
});

export {expect};
