const fs = require('fs');
const path = require('path');

// Путь к папке с API
const apiPath = path.join(__dirname, 'src/api');

// Функция для создания модели (schema.json)
function createModel(name, attributes, relations = {}) {
  const modelPath = path.join(apiPath, name, 'content-types', name);
  const schemaPath = path.join(modelPath, 'schema.json');

  // Создаем папки
  fs.mkdirSync(modelPath, { recursive: true });

  // Создаем JSON-схему
  const schema = {
    kind: 'collectionType',
    collectionName: `${name}s`,
    info: {
      singularName: name,
      pluralName: `${name}s`,
      displayName: name,
    },
    options: {
      draftAndPublish: true,
    },
    pluginOptions: {},
    attributes: {
      ...attributes,
      ...relations,
    },
  };

  // Записываем схему в файл
  fs.writeFileSync(schemaPath, JSON.stringify(schema, null, 2));
  console.log(`Модель ${name} создана: ${schemaPath}`);
}

// Функция для создания маршрутов (routes) с публичным доступом
function createRoutes(name) {
  const routesDir = path.join(apiPath, name, 'routes');
  const routePath = path.join(routesDir, `${name}.js`);
  fs.mkdirSync(routesDir, { recursive: true });
  const routesContent = `module.exports = {
  routes: [
    {
      method: 'GET',
      path: '/${name}s',
      handler: '${name}.find',
      config: {
        auth: false,
      },
    },
    {
      method: 'GET',
      path: '/${name}s/:id',
      handler: '${name}.findOne',
      config: {
        auth: false,
      },
    },
    {
      method: 'POST',
      path: '/${name}s',
      handler: '${name}.create',
      config: {
        auth: false,
      },
    },
    {
      method: 'PUT',
      path: '/${name}s/:id',
      handler: '${name}.update',
      config: {
        auth: false,
      },
    },
    {
      method: 'DELETE',
      path: '/${name}s/:id',
      handler: '${name}.delete',
      config: {
        auth: false,
      },
    },
  ],
};
`;
  fs.writeFileSync(routePath, routesContent);
  console.log(`Маршруты для модели ${name} созданы: ${routePath}`);
}

// Функция для создания контроллера с базовыми CRUD-методами
function createController(name) {
  const controllerDir = path.join(apiPath, name, 'controllers');
  const controllerPath = path.join(controllerDir, `${name}.js`);
  fs.mkdirSync(controllerDir, { recursive: true });
  const controllerContent = `module.exports = {
  async find(ctx) {
    return await strapi.entityService.findMany('api::${name}.${name}', ctx.query);
  },
  async findOne(ctx) {
    return await strapi.entityService.findOne('api::${name}.${name}', ctx.params.id, ctx.query);
  },
  async create(ctx) {
    return await strapi.entityService.create('api::${name}.${name}', { data: ctx.request.body });
  },
  async update(ctx) {
    return await strapi.entityService.update('api::${name}.${name}', ctx.params.id, { data: ctx.request.body });
  },
  async delete(ctx) {
    return await strapi.entityService.delete('api::${name}.${name}', ctx.params.id);
  },
};
`;
  fs.writeFileSync(controllerPath, controllerContent);
  console.log(`Контроллер для модели ${name} создан: ${controllerPath}`);
}

// Функция для создания полной структуры модели (schema, routes, controller)
function createFullModel(name, attributes, relations = {}) {
  createModel(name, attributes, relations);
  createRoutes(name);
  createController(name);
}

// Создаем модель продукта
createFullModel('product', {
  title: { type: 'string', required: true },
  price: { type: 'decimal', required: true },
  description: { type: 'text' },
  picture: { type: 'media', multiple: false, required: true }
});

// Создаем модель клиента
createFullModel('client', {
  tg_id: { type: 'string', required: true },
  email: { type: 'email' },
});

// Создаем модель корзины
createFullModel('cart', {
  tg_id: { type: 'string', required: true },
}, {
  client: {
    type: 'relation',
    relation: 'oneToOne',
    target: 'api::client.client',
  },
  cart_items: {
    type: 'relation',
    relation: 'oneToMany',
    target: 'api::cart-item.cart-item',
    mappedBy: 'cart'
  }
});

// Создаем модель элемента корзины
createFullModel('cart-item', {
  quantity: { type: 'integer', required: true },
}, {
  cart: {
    type: 'relation',
    relation: 'manyToOne',
    target: 'api::cart.cart',
  },
  product: {
    type: 'relation',
    relation: 'manyToOne',
    target: 'api::product.product',
  },
});

console.log('✅ Все модели успешно созданы!');
